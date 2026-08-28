# Publish Background Task Terminals After Cleanup

Background tasks now keep cancellation and mission-timeout requests non-terminal until their
owned coroutine has completed child Session cleanup. Model-budget failures continue through the
typed run-error path, and completion waiters are released only after cleanup has finished.
