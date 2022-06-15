"""
Client utility, to test out fHDHR (and Ceton, with the 'default' configuration as captured below.

Run parameters as captured below => when started, randomly delays and starts client runners (ffmpeg), that
access / use tuners, based on the default command (also below). By editing the command, HW encoding can be used (or
not), and the output can be redirected to a file if desired (for checking - the default is output to /dev/null).
"""

__version__ = '1.1.0'

from collections import namedtuple
import random
import sched
import time
import threading
import subprocess

# Define named tuples (for usage below)
timedefn = namedtuple('timedefn', ['min', 'max'])
jobtime = namedtuple('jobtime', ['delay', 'runtime'])

# Define run parameters
jobcnt = 3                                      # Number of jobs / runners (i.e. jobs to run)
chanlist = [505, 593, 508, 553]                 # Channel list (to use, cycle through them)
outlist = ['-f null /dev/null',                 # List, of output destination (null, file, etc.)
           '-f null /dev/null',
           '-f null /dev/null',
           '-f mpegts /dev/null']
totalrun = 1200                                 # Total run time, seconds. Will stop at this point.
timedly = timedefn(5, 15)                       # Time delay before start job, range in seconds
timerun = timedefn(10, 30)                      # Time to run a (ffmpeg) job, range in seconds
startzero = True                                # Start all jobs at zero time (vs. timedly, random value)

# ffmpeg command - default. DUR is replaced by run duration, CHNL by the targeted channel
ffmpegcli = 'ffmpeg -y -loglevel error -hwaccel cuda -hwaccel_output_format cuda ' \
            '-i http://192.168.2.64:5006/api/tuners?method=stream&channel=CHNL&origin=ceton -t DUR ' \
            '-vf scale_cuda=1920:1080 -c:v hevc_nvenc -preset p6 -tune hq -b:v 3M -c:a ac3 -b:a 196k'

# And, some counters / tracking variables
currchnl = 0                                    # Current channel to be used (index to chanlist)
exitcode = 0                                    # Exit Code, start assuming all is good

# Routine to provide random delay and run time - based on desired ranges for each
def timing(immediate):
    delay = random.randint(timedly.min, timedly.max)
    runtime = random.randint(timerun.min, timerun.max)
    if immediate:
        delay = 0
    return jobtime(delay, runtime)


# Routine to start a job (ffmpeg runner)
# Adapted from, https://stackoverflow.com/questions/2581817/python-subprocess-callback-when-cmd-exits
def runner(job):
    global currchnl
    # Build command to execute, selecting desired channel for the particular job
    ffmpegcmd = ffmpegcli
    ffmpegcmd = ffmpegcmd.replace("CHNL", str(chanlist[currchnl]))
    ffmpegcmd = ffmpegcmd.replace("DUR", str(job['timing'].runtime))
    ffmpegcmd = ffmpegcmd + ' ' + outlist[currchnl]
    # Store info to job, step to next channel (modulo)
    job['ffmpegcmd'] = ffmpegcmd
    job['currchnl'] = currchnl
    currchnl = (currchnl + 1) % len(chanlist)
    """
    Runs the given args in a subprocess.Popen, and then calls the function
    on_exit when the subprocess completes.
    on_exit is a callable object, and popen_args is a list/tuple of args that 
    would give to subprocess.Popen.
    """
    def run_in_thread(on_exit, popen_args, threadjob):
        global exitcode
        # Non-blocking process run (Popen)!
        # Shell not requird for POSIX, but then have to split string to array (not if Shell=True!)
        # Store process information, so can terminate() at the exit (cleanly!) of this program overall
        #
        # NOTE: Not launched with shell=True, so can just terminate() if needed (to end overall program)
        # https://stackoverflow.com/questions/4789837/how-to-terminate-a-python-subprocess-launched-with-shell-true
        # NOTE: Just run to test fHDHR / Ceton (plugin), so don't set check=True (and handle exceptions). Rather,
        # just watch the console output if desired => otherwise, just use as a test tool.
        proc = subprocess.Popen(popen_args)
        threadjob['proc'] = proc
        print("[%s] Starting Job: %d (Duration = %d secs), PID = %s" %
              (time.asctime(time.localtime(time.time())), threadjob['job'], threadjob['timing'].runtime, str(proc.pid)))
        proc.wait()
        print("[%s] Ending Job: %d, PID = %s" %
              (time.asctime(time.localtime(time.time())), threadjob['job'], str(proc.pid)))
        if proc.returncode:
            exitcode = exitcode + 1
        if threadjob['restart']:
            on_exit(threadjob, False)
        return
    thread = threading.Thread(target=run_in_thread, args=(newrunner, ffmpegcmd.split(), job))
    thread.start()
    return thread


# Routine called to create a new runner => also when (ffmpeg job) exits - set up the next job, keep them cycling!
# NOTE: Each runner has it's own scheduler ... simple, and because cannot add dynamically after scheduler.run()
def newrunner(job, immediate=False):
    job['timing'] = timing(immediate)
    job['restart'] = True
    print("[%s] Scheduling New Job: %d (Delay = %d secs, Duration = %d secs)"
          % (time.asctime(time.localtime(time.time())), job['job'], job['timing'].delay, job['timing'].runtime))
    job['event'] = job['sched'].enter(job['timing'].delay, job['job'], runner, argument=(job,))
    # Run schedule, non-blocking => launches execution (controlled in that thread itself!), then returns for next job
    job['sched'].run(blocking=True)


# Routine to exit - remove all jobs, and return => scheduler will autonomously exit, cleanly
def endrunners(alljobs):
    print("[%s] Stopping All Jobs ..." % time.asctime(time.localtime(time.time())))
    for killjob in alljobs:
        # Handle the case of scheduled jobs (i.e. waiting to start ffmpeg)
        if len(killjob['sched'].queue) == 1:
            print('   > Stopping (sched) Priority: %d' % killjob['event'].priority)
            killjob['sched'].cancel(killjob['event'])
        # Also, handle if ffmpeg is actively running
        if 'proc' in killjob:
            print('   > Killing (ffmpeg) Process: %d' % killjob['proc'].pid)
            killjob['restart'] = False
            killjob['proc'].terminate()


# Routine to print the scheduler queue (formatted)
def printqueue(alljobs):
    print('[%s] Scheduler Queue (runners) ... ' % time.asctime(time.localtime(time.time())))
    for prtjob in alljobs:
        print('   > Priority (job): %d, Time: %d' % (prtjob['event'].priority, prtjob['event'].time - start))


# Press the green button in the gutter to run the script.
# Main Routine - get WireGuard dump (information), process and write out to influx
if __name__ == '__main__':
    # Store the program start time
    start = time.time()
    print('Start Time: [%s]' % time.asctime(time.localtime(time.time())))
    # Create runners (jobs) - each with their own scheduler, to allow dynamic updates (new job starts)
    runners = []
    for currjob in range(jobcnt):
        runners.append({'job': currjob})
        currrunner: dict = runners[-1]
        currrunner['sched'] = sched.scheduler(time.time, time.sleep)
        newrunner(currrunner, startzero)
    printqueue(runners)
    # And add long-running (full duration) job, then start the scheduler (blocking, so only exit in a controlled way)
    fullsched = sched.scheduler(time.time, time.sleep)
    fullsched.enter(totalrun, -1, endrunners, argument=(runners,))
    fullsched.run(blocking=True)

    if exitcode:
        print('Exiting, with Errors.')
    else:
        print('Exiting Cleanly!')
    exit(exitcode)
