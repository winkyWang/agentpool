# Isolate background notification cancellation

Background-task notification batching now owns and closes its timer and flush
task handles directly. It no longer enters an AnyIO cancellation scope on the
calling request task, preventing completed OpenCode requests from leaving the
server event loop in a permanent cancellation-delivery spin.
