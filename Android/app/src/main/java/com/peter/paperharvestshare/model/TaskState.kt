package com.peter.paperharvestshare.model

enum class TaskState {
    ENQUEUED,
    RUNNING,
    RETRYING,
    SUCCEEDED,
    FAILED,
    CANCELLED,
}
