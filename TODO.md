# TODO

## Features

* Test files deleted or not accessible mid-run
* Test recovery: interruption during tar
* Test recovery: interruption during upload
* Support restoring files (single, multiple, whole backup)
* Support configured temp dir
* Support exclusions
* Support pruning archives that are no longer relevant

## Pruning obsolete archives

* Build list of files that are x% irrelevant and older than y days (y at least 180)
    * Improve this with a function that relates age to irrelevance: e.g. age = 180 + relevance_ratio * 180, where 0 <= relevance_ratio < 1
    * Should also factor in the size. Maybe age = 180 + relevance_ratio * (size/target_size) * 180
* Flag archives as pending deletion
* Update files table to flag files that are going to need new backups (need variant of mark_files_for_backup())
* Run backups
* If successful, delete archives pending deletion from AWS
* Flag archives as deleted and update f_a_r (and files table out of precaution? raise error if any update happens?)
