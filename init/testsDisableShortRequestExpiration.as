#
#	testDisableShortRequestExpiration.as
#
#	This script is supposed to be called by the test system via the upper tester interface
#

@name disableShortRequestExpiration
@description (Tests) Disable shorter request expirations
@usage disableShortRequestExpiration
@uppertester

if ${argc} > 0
	error Wrong number of arguments: disableShortRequestExpiration
	quit
endif

##################################################################

# Restore the CSE's request expiration check
if ${storageHas cse.requestExpirationDelta}
	setConfig cse.requestExpirationDelta ${storageGet cse.requestExpirationDelta}
	storageRemove cse.requestExpirationDelta
endif

