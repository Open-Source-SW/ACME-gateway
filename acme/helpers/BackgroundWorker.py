#
#	BackgroundWorker.py
#
#	(c) 2020 by Andreas Kraft
#	License: BSD 3-Clause License. See the LICENSE file for further details.
#
#	This class implements a background process.
#

""" A pool for background workers, actors, and jobs. """

from __future__ import annotations
from codecs import strict_errors
from os import times
from sqlite3 import Timestamp
from .TextTools import simpleMatch
import random, sys, heapq, datetime, traceback, time
from threading import Thread, Timer, Event, RLock, Lock, enumerate as threadsEnumerate
from typing import Callable, List, Dict, Any, Tuple
import logging


def _utcTime() -> float:
	"""	Return the current time's timestamp, but relative to UTC.

		Return:
			Float UTC-based timestamp
	"""
	return datetime.datetime.utcnow().timestamp()


class BackgroundWorker(object):
	"""	This class provides the functionality for background worker or a single actor instance.
	"""

	# Holds a reference to an specific logging function.
	# This must have the same signature as the `logging.log` method.
	_logger:Callable[[int, str], None] = logging.log


	def __init__(self,
						interval:float,
						callback:Callable, 
						name:str = None, 
						startWithDelay:bool = False,
						maxCount:int = None, 
						dispose:bool = True, 
						id:int = None, 
						runOnTime:bool = True, 
						runPastEvents:bool = False, 
						finished:Callable = None,
						ignoreException:bool = False,
						data:Any = None) -> None:
		self.interval 				= interval
		self.runOnTime				= runOnTime			# Compensate for processing time
		self.runPastEvents			= runPastEvents		# Run events that are in the past
		self.nextRunTime:float		= None				# Timestamp
		self.callback 				= callback			# Actual callback to process
		self.running 				= False				# Indicator that a worker is running or will be stopped
		self.executing				= False				# Indicator that the worker callback is currently executed
		self.name 					= name
		self.startWithDelay 		= startWithDelay
		self.maxCount 				= maxCount			# max runs
		self.numberOfRuns 			= 0					# Actual runs
		self.dispose 				= dispose			# Only run once, then remove itself from the pool
		self.finished				= finished			# Callback after worker finished
		self.ignoreException		= ignoreException	# Ignore exception when running workers
		self.id 					= id
		self.data					= data				# Any extra data



	def start(self, **kwargs:Any) -> BackgroundWorker:
		"""	Start the background worker in a thread. 
		
			If the background worker is already	running then it is stopped and started again.

			Args:
				kwargs: Any number of keyword arguments are passed to the worker.

			Return:
				The background worker instance.
		"""

		if self.running:
			self.stop()
		if BackgroundWorker._logger:
				BackgroundWorker._logger(logging.DEBUG, f'Starting {"actor" if self.maxCount and self.maxCount > 0 else "worker"}: {self.name}')
		# L.isDebug and L.logDebug(f'Starting {"worker" if self.interval > 0.0 else "actor"}: {self.name}')
		self.numberOfRuns	= 0
		self.args 			= kwargs
		self.running 		= True
		realInterval 		= self.interval if self.startWithDelay else 0	# first interval
		self.nextRunTime 	= _utcTime() + realInterval			# now + interval (or 0)
		BackgroundWorkerPool._queueWorker(self.nextRunTime, self)
		return self


	def stop(self) -> BackgroundWorker:
		"""	Stop the background worker.

			Return:
				The background worker instance.
		"""
		if not self.running:
			return self
		self.running = False
		if BackgroundWorker._logger:
				BackgroundWorker._logger(logging.DEBUG, f'Stopping {"actor" if self.maxCount and self.maxCount > 0 else "worker"}: {self.name}')
		BackgroundWorkerPool._unqueueWorker(self)		# Stop the timer and remove from queue
		self._postCall()									# Note: worker is removed in _postCall()
		return self
	

	def restart(self, interval:float = None) -> BackgroundWorker:
		"""	Restart the worker. Optionally use new interval, and re-use the previous arguments passed with the `start()` method.
		
			Args:
				interval: Optional float with the interval.

			Return:
				The background worker instance, or None if the worker isn't running
		"""
		if not self.running:
			return None
		self.pause()
		if interval is not None:
			self.interval = interval
		return self.unpause()
	

	def pause(self) -> BackgroundWorker:
		"""	Pause the execution of a a worker.

			Return:
				The background worker instance.
		"""
		if not self.running:
			return self
		while self.executing:	# Wait until the worker is finished executing its current turn
			time.sleep(0.001)
		BackgroundWorkerPool._unqueueWorker(self)
		return self


	def unpause(self, immediately:bool = False) -> BackgroundWorker:
		""" Continue the running of a worker. 

			Args:
				immediately: If True then the worker is executed immediately, and then the normal schedule continues.
			Return:
				self.
		"""
		if not self.running:
			return None
		self.nextRunTime = _utcTime() if immediately else _utcTime() + self.interval		# timestamp for next interval (interval + time from end of processing)
		BackgroundWorkerPool._queueWorker(self.nextRunTime, self)
		return self


	def workNow(self) -> BackgroundWorker:
		"""	Execute the worker right immediately and outside the normal schedule.

			Return:
				self.
		"""
		if self.executing:
			return self
		self.pause()
		self.unpause(immediately=True)
		return self


	def _work(self) -> None:
		"""	Wrapper around the actual worker function. It deals with terminating,
			process time compensation, etc.

			This wrapper and the callback are executed in a separate Thread.
			At the end, depending on return value and whether the maxCount has been reached, the worker is added to the queue again.
		"""
		if not self.running:
			return
		result = True
		try:
			self.numberOfRuns += 1
			self.executing = True

			# The following calls the worker callback.
			# If there is no exception, then the loop is left
			# If there is an exception and
			# - ignoreException is True then the loop is run again
			# - ignoreException is False then the exception is raised again
			while True:
				try:
					if self.data is not None:
						result = self.callback(_data = self.data, **self.args)
					else:
						result = self.callback(**self.args)
					break
				except Exception as e:
					if BackgroundWorker._logger:
						# FIXME remove when really supporting 3.10
						if sys.version_info < (3, 10):
							BackgroundWorker._logger(logging.ERROR, f'Worker "{self.name}" exception during callback {self.callback.__name__}: {str(e)}\n{"".join(traceback.format_exception(etype = type(e), value = e, tb = e.__traceback__))}')
						else:
							BackgroundWorker._logger(logging.ERROR, f'Worker "{self.name}" exception during callback {self.callback.__name__}: {str(e)}\n{"".join(traceback.format_exception(type(e), value = e, tb = e.__traceback__))}')
					if self.ignoreException:
						continue
					raise

		except SystemExit:
			quit()

		except Exception as e:

			if BackgroundWorker._logger:
				# FIXME remove when really supporting 3.10
				if sys.version_info < (3, 10):
					BackgroundWorker._logger(logging.ERROR, f'Worker "{self.name}" exception during callback {self.callback.__name__}: {str(e)}\n{"".join(traceback.format_exception(etype = type(e), value = e, tb = e.__traceback__))}')
				else:
					BackgroundWorker._logger(logging.ERROR, f'Worker "{self.name}" exception during callback {self.callback.__name__}: {str(e)}\n{"".join(traceback.format_exception(type(e), value = e, tb = e.__traceback__))}')
		finally:
			self.executing = False
			if not result or (self.maxCount and self.numberOfRuns >= self.maxCount):
				# False returned, or the numberOfRuns has reached the maxCount
				self.stop()
				# Not queued anymore after this run, but the Timer is restarted in stop()
			else:
				now = _utcTime()
				while True:
					if self.runOnTime:									# compensate for processing time?
						self.nextRunTime += self.interval				# timestamp for next interval (fixed interval)
					else:
						self.nextRunTime =  now + self.interval			# timestamp for next interval (interval + time from end of processing)
					if now < self.nextRunTime or self.runPastEvents:	# check whether to increment nextRunTime again (and again...)
						break

				BackgroundWorkerPool._queueWorker(self.nextRunTime, self)		# execute at nextRunTime


	def _postCall(self) -> None:
		"""	Internal cleanup after execution finished.
		"""
		if self.finished:
			self.finished(**self.args)
		if self.dispose:
			BackgroundWorkerPool._removeBackgroundWorkerFromPool(self)


	def __repr__(self) -> str:
		return f'BackgroundWorker(name={self.name}, callback = {str(self.callback)}, running = {self.running}, interval = {self.interval:f}, startWithDelay = {self.startWithDelay}, numberOfRuns = {self.numberOfRuns:d}, dispose = {self.dispose}, id = {self.id}, runOnTime = {self.runOnTime})'



class Job(Thread):
	"""	Job class that extends the *Thread* class with pause, resume, stop functionalities, and lists of
		running and paused jobs for reuse.

		Job objects are not deleted immediately after they finished but pooled for reuse. They are
		only destroyed when the pressure on the pool was low for a certain time.
	"""

	jobListLock	= RLock()			# Re-entrent lock (for the same thread)

	# Paused and running job lists
	pausedJobs:list[Job] = []
	runningJobs:list[Job] = []

	# Defaults for reducing overhead jobs
	_balanceTarget:float = 3.0			# Target balance between paused and running jobs (n paused for 1 running)
	_balanceLatency:int = 1000			# Number of requests for getting a new Job before a check
	_balanceReduceFactor:float = 2.0	# Factor to reduce the paused jobs (number of paused / balanceReduceFactor)
	_balanceCount:int = 0				# Counter for current runs. Compares against balance


	def __init__(self, *args:Any, **kwargs:Any) -> None:
		"""	Initialize a Job object.
		
			Args:
				args: Positional job arguments.
				kwargs: Keyword job arguments.
		"""

		super(Job, self).__init__(*args, **kwargs)
		self.setDaemon(True)

		self.pauseFlag = Event()
		""" The flag used to pause the thread """

		self.pauseFlag.set()
		""" Set to True when the job is **not** paused. """

		self.activeFlag = Event() 
		""" Indicates that a job is active. An active job might be paused. """
		self.activeFlag.set() # Set active to True

		self.task:Callable = None
		""" Callback for the job's task. """

		self.finished:Callable = None
		""" Optional callback that is called after the `task` finished. """


	def run(self) -> None:
		"""	Internal runner function for a job.
		"""
		while self.activeFlag.is_set():
			self.pauseFlag.wait() # return immediately when it is True, block until the internal flag is True when it is False
			if not self.activeFlag.is_set():
				break
			if self.task:
				self.task()
				self.task = None
			if self.finished:
				self.finished(self)
				self.finished = None
			self.pause()


	def pause(self) -> Job:
		"""	Pause a thread job. The job is removed from the running list
			(if still present there) and moved to the paused list.
		
			Return:
				The Job object.
		"""
		with Job.jobListLock:
			if self in Job.runningJobs:
				Job.runningJobs.remove(self)
			Job.pausedJobs.append(self)
		self.pauseFlag.clear() # Block the thread
		return self


	def resume(self) -> Job:
		"""	Resume a thread job. The job is removed from the paused list
			(if still present there) and moved to the running list.
		
			Return:
				The Job object.
		"""
		with Job.jobListLock:
			if self in Job.pausedJobs:
				Job.pausedJobs.remove(self)
			Job.runningJobs.append(self)
		self.pauseFlag.set() # Stop blocking
		return self


	def stop(self) -> Job:
		"""	Stop a thread job

			Return:
				The Job object.
		"""
		self.activeFlag.clear() # Stop the thread
		self.pauseFlag.set() # Resume the thread from the suspended state
		if self in Job.runningJobs:
			Job.runningJobs.remove(self)
		if self in Job.pausedJobs:
			Job.runningJobs.remove(self)
		return self
	

	def setTask(self, task:Callable, finished:Callable = None, name:str = None) -> Job:
		"""	Set a task to run for the Job.
		
			Args:
				task: A Callable. This must include arguments, so a lambda can be used here.
				finished: A Callable that is called when the task finished.
				name: Optional name of the job.
			Return:
				The Job object.
		"""
		self.setName(name)
		self.task = task
		self.finished = finished
		return self
	

	@classmethod
	def getJob(cls, task:Callable, finished:Callable = None, name:str = None) -> Job:
		"""	Get a Job object, and set a task and a finished Callable for it to execute.
			The Job object is either taken from the paused list (if available), or
			a new one is created.
			After calling this method the Job instance is neither in the paused nor the
			running list. It is moved into the running list, for example, with the `resume()`
			method.

			Args:
				task: A Callable. This must include arguments, so a lambda can be used here.
				finished: A Callable that is called when the task finished.
				name: Optional name of the job.
			Return:
				The Job object.
		"""
		with Job.jobListLock :
			if not Job.pausedJobs:
				job = Job().pause()	# new job and internal pause before start
				job.start() # start the thread, but since it is paused, it will not run the task

			job = Job.pausedJobs.pop(0).setTask(task, finished, name)	# remove next job from paused list and set the task parameter
			Job._balanceJobs()	# check the pause/running jobs balance
			return job
	

	@classmethod
	def _balanceJobs(cls) -> None:
		if not Job._balanceLatency:
			return
		Job._balanceCount += 1
		if Job._balanceCount >= Job._balanceLatency:		# check after balancyLatency runs
			if float(lp := len(Job.pausedJobs)) / float(len(Job.runningJobs)) > Job._balanceTarget:				# out of balance?
				for _ in range((int(lp / Job._balanceReduceFactor))):
					Job.pausedJobs.pop(0).stop()
			Job._balanceCount = 0


	@classmethod
	def setJobBalance(cls, balanceTarget:float = 3.0, balanceLatency:int = 1000, balanceReduceFactor:float = 2.0) -> None:
		"""	Set parameters to balance the number of paused Jobs.

			Args:
				balanceTarget: Target balance between paused and running jobs (n paused for 1 running).
				balanceLatency: Number of requests for getting a new Job before a balance check.
				balanceReduceFactor: Factor to reduce the paused jobs (number of paused / balanceReduceFactor).	
		"""
		cls._balanceTarget = balanceTarget
		cls._balanceLatency = balanceLatency
		cls._balanceReduceFactor = balanceReduceFactor


class WorkerEntry(object):
	timestamp:float = 0.0
	workerID:int = None
	workerName:str = None

	def __init__(self, timestamp:float, workerID:int, workerName:str) -> None:
		self.timestamp = timestamp
		self.workerID = workerID
		self.workerName = workerName


	def __lt__(self, other:WorkerEntry) -> bool:
		return self.timestamp < other.timestamp

	
	def __str__(self) -> str:
		return f'(ts: {self.timestamp} id: {self.workerID} name: {self.workerName})'
	

	def __repr__(self) -> str:
		return self.__str__()


class BackgroundWorkerPool(object):
	"""	Pool and factory for background workers and actors.
	"""
	backgroundWorkers:Dict[int, BackgroundWorker]	= {}
	workerQueue:list[WorkerEntry] 					= []
	""" Priority queue. Contains tuples (next execution timestamp, worker ID, worker name). """
	workerTimer:Timer								= None
	"""	A single timer to run the next task in the *workerQueue*. """

	queueLock:Lock					 				= Lock()
	timerLock:Lock					 				= Lock()


	def __new__(cls, *args:str, **kwargs:str) -> BackgroundWorkerPool:
		"""	Prevent from instantiation.
		
			This class has static functions only.
		"""
		raise TypeError(f'{BackgroundWorkerPool.__name__} must not be instantiated')
	

	@classmethod
	def setLogger(cls, logger:Callable) -> None:
		"""	Assign a callback for logging.

			Args:
				logger: Logging callback.
		"""
		BackgroundWorker._logger = logger


	@classmethod
	def setJobBalance(cls, balanceTarget:float = 3.0, balanceLatency:int = 1000, balanceReduceFactor:float = 2.0) -> None:
		"""	Set parameters to balance the number of paused Jobs.

			Args:
				balanceTarget: Target balance between paused and running jobs (n paused for 1 running).
				balanceLatency: Number of requests for getting a new Job before a balance check.
				balanceReduceFactor: Factor to reduce the paused jobs (number of paused / balanceReduceFactor).	
		"""
		Job.setJobBalance(balanceTarget, balanceLatency, balanceReduceFactor)


	@classmethod
	def newWorker(cls,	interval:float, 
						workerCallback:Callable,
						name:str = None, 
						startWithDelay:bool = False, 
						maxCount:int = None, 
						dispose:bool = True, 
						runOnTime:bool = True, 
						runPastEvents:bool = False, 
						finished:Callable = None, 
						ignoreException:bool = False,
						data:Any = None) -> BackgroundWorker:	# type:ignore[type-arg]
		"""	Create a new background worker that periodically executes the callback.

			Args:
				interval: Interval in seconds to run the worker callback
				workerCallback: Callback to run as a worker
				name: Name of the worker
				startWithDelay: If True then start the worker after a `interval` delay 
				maxCount: Maximum number runs
				dispose: If True then dispose the worker after finish.
				runOnTime: If True then the worker is always run *at* the interval, otherwise the interval starts *after* the worker execution.
				runPastEvents: If True then runs in the past are executed, otherwise they are dismissed.
				finished: Callable that is executed after the worker finished.
				ignoreException: Restart the actor in case an exception is encountered.
				data: Any data structure that is stored in the worker and accessible by the *data* attribute, and which is passed as the first argument in the *_data* argument of the *workerCallback* if not *None*.

			Return:
				BackgroundWorker

		"""
		# Get a unique worker ID
		while True:
			if (id := random.randint(1,sys.maxsize)) not in cls.backgroundWorkers:
				break
		worker = BackgroundWorker(interval, 
								  workerCallback, 
								  name, 
								  startWithDelay, 
								  maxCount = maxCount, 
								  dispose = dispose, 
								  id = id, 
								  runOnTime = runOnTime, 
								  runPastEvents = runPastEvents, 
								  ignoreException = ignoreException,
								  data = data)
		cls.backgroundWorkers[id] = worker
		return worker


	@classmethod
	def newActor(cls,	workerCallback:Callable, 
						delay:float = 0.0, 
						at:float = None, 
						name:str = None, 
						dispose:bool = True, 
						finished:Callable = None, 
						ignoreException:bool = False,
						data:Any = None) -> BackgroundWorker:
		"""	Create a new background worker that runs only once after a *delay*
			(it may be 0.0s, though), or *at* a specific time (UTC timestamp).

			Args:
				workerCallback: Callback that is executed to perform the action for the actor.
				delay: Delay in seconds after which the actor callback is executed.
					This is an alternative to *at*.
					Only one of *at* or *delay* must be specified.
				at: Run the actor at a specific time (timestamp). 
					This is an alternative to *delay*.
					Only one of *at* or *delay* must be specified.
				name: Name of the actor.
				dispose: If True then dispose the actor after finish.
				finished: Callable that is executed after the worker finished.
					It will	receive the same arguments as the *workerCallback* callback.
				ignoreException: Restart the actor in case an exception is encountered.
				data: Any data structure that is stored in the worker and accessible by the *data* attribute, and which is passed as the first argument in the *_data* argument of the *workerCallback* if not *None*.
			Return:
				`BackgroundWorker` object. It is only an initialized object and needs to be started manually with its `start()` method.
		"""
		if at:
			if delay != 0.0:
				raise ValueError('Cannot set both "delay" and "at" arguments')
			delay = at - _utcTime()
		return cls.newWorker(delay, 
							 workerCallback, 
							 name = name, 
							 startWithDelay = delay > 0.0, 
							 maxCount = 1, 
							 dispose = dispose, 
							 finished = finished, 
							 ignoreException = ignoreException,
							 data = data)


	@classmethod
	def findWorkers(cls, name:str = None, running:bool = None) -> List[BackgroundWorker]:
		"""	Find and return a list of worker(s) that match the search criteria.

			Args:
				name: Name of the worker. It may contain simple wildcards (* and ?).
					If *name* is None then stop all workers.
				running: The running status of the worker to match
			
			Return:
				A list of `BackgroundWorker` objects, or an empty list.
		"""
		return [ w for w in cls.backgroundWorkers.values() if (not name or simpleMatch(w.name, name)) and (not running or running == w.running) ]


	@classmethod
	def stopWorkers(cls, name:str = None) -> List[BackgroundWorker]:
		"""	Stop the worker(s) that match the optional *name* parameter. 

			Args:
				name: Name of the worker(s) to remove. It may contain simple wildcards (* and ?).
					If *name* is None then stop all workers.
			Return:
				The list of removed `BackgroundWorker` objects.
		"""
		workers = cls.findWorkers(name = name)
		for w in workers:
			w.stop()
		return workers


	@classmethod
	def removeWorkers(cls, name:str) -> List[BackgroundWorker]:
		"""	Remove workers from the pool. Before removal they will be stopped first.

			Only workers that match the *name* are removed.

			Args:
				name: Name of the worker(s) to remove. It may contain simple wildcards (* and ?).
			Return:
				The list of removed `BackgroundWorker` objects.
		"""
		workers = cls.stopWorkers(name)
		# Most workers should be removed when stopped, but remove the rest here
		for w in workers:
			cls._removeBackgroundWorkerFromPool(w)
		return workers


	#
	#	Jobs
	#

	@classmethod
	def runJob(cls, task:Callable, name:str = None) -> Job:
		"""	Run a task as a Thread. Reuse finished threads if possible.

			Args:
				task: A Callable that is run as a job. This must include arguments, so a lambda can be used here.
				name: Optional name of the job.
			Return:
				`Job` instance.
		"""
		return Job.getJob(task, name = name).resume()


	@classmethod
	def countJobs(cls) -> Tuple[int, int]:
		"""	Return the number of running and paused Jobs.
		
			Return:
				Tuple of the integer numbers (count of running and paused `Job` instances).
		"""
		return (len(Job.runningJobs), len(Job.pausedJobs))


	@classmethod
	def killJobs(cls) -> None:
		"""	Stop and remove all Jobs.
		"""
		while Job.runningJobs:
			# Job.runningJobs.pop(0).stop()
			Job.runningJobs[0].stop()	# will remove itself
		while Job.pausedJobs:
			Job.pausedJobs[0].stop()	# will remove itself
		while any( [ isinstance(each, Job) for each in threadsEnumerate() ] ):
			time.sleep(0.00001)


	#
	#	Internals
	#

	@classmethod
	def _removeBackgroundWorkerFromPool(cls, worker:BackgroundWorker) -> None:
		"""	Remove a *BackgroundWorker* object from the internal pool.
		
			Args:
				worker: Backgroundworker objects to remove.
			"""
		if worker and worker.id in cls.backgroundWorkers:
			del cls.backgroundWorkers[worker.id]


	@classmethod
	def _queueWorker(cls, ts:float, worker:BackgroundWorker) -> None:
		"""	Queue a `BackgroundWorker` object for execution at the *ts* timestamp.

			Args:
				ts: Timestamp at which the worker shall be executed.
				worker: Backgroundworker object to queue.
		"""
		top = cls.workerQueue[0] if cls.workerQueue else None
		with cls.queueLock:
			cls._stopTimer()
			heapq.heappush(cls.workerQueue, WorkerEntry(ts, worker.id, worker.name))
			cls._startTimer()


	@classmethod
	def _unqueueWorker(cls, worker:BackgroundWorker) -> None:
		"""	Remove the Backgroundworker for `id` from the queue.

			Args:
				worker: Backgroundworker to unqueue
		"""
		with cls.queueLock:
			cls._stopTimer()
			for each in cls.workerQueue:
				if each.workerID == worker.id:
					cls.workerQueue.remove(each)
					heapq.heapify(cls.workerQueue)
					break	# Only 1 worker
			cls._startTimer()


	@classmethod
	def _startTimer(cls) -> None:
		""" Start the workers queue timer.
		"""
		if cls.workerQueue:
			with cls.timerLock:
				if cls.workerTimer is not None:	# don't start another timer!
					return
				cls.workerTimer = Timer(cls.workerQueue[0].timestamp - _utcTime(), cls._execQueue)
				cls.workerTimer.setDaemon(True)	# Make the Timer thread a daemon of the main thread
				cls.workerTimer.start()
	

	@classmethod
	def _stopTimer(cls) -> None:
		"""	Cancel/interrupt the workers queue timer.
		"""
		with cls.timerLock:
			if cls.workerTimer is not None:
				cls.workerTimer.cancel()
				cls.workerTimer = None


	@classmethod
	def _execQueue(cls) -> None:
		"""	Execute the actual BackgroundWorker's callback in a thread.
		"""
		with cls.queueLock:
			cls._stopTimer()
			if cls.workerQueue:
				w = heapq.heappop(cls.workerQueue)
				if worker := cls.backgroundWorkers.get(w.workerID):
					cls.runJob(worker._work, w.workerName)
			cls._startTimer()	# start timer again

