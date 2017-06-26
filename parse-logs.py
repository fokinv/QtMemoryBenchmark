#!/usr/bin/env python

import re
import sys
import itertools
import collections
MAX_SNAPSHOT_DIFF = 1000000
TO_KILO = 1024
TO_MEGA = 1024*1024


class MassifOutput(object):
    def __init__(self, file_name):
        self.file_name = file_name
        log_file = open(file_name, "r")
        self.snapshots = self._parse_snapshots(log_file)
        log_file.close()

    class States(object):
        NONE = 0
        ID = 1
        CONTENT = 2

    def get_file_name(self):
        return self.file_name

    def get_snapshots(self):
        return self.snapshots

    def _parse_snapshots(self, log_file):
        current_id = None
        state = self.States.NONE
        snapshots = {}
        for line in log_file:
            if re.match("^#-*$", line):
                if state is self.States.NONE:
                    state = self.States.ID
                    continue
                if state is self.States.ID:
                    state = self.States.CONTENT
                    continue
                if state is self.States.CONTENT:
                    state = self.States.ID
                    continue
                else:
                    raise RuntimeError("Something totally unexpected happened.")

            if state is self.States.ID:
                split_line = line.split("=")
                if len(split_line) is not 2 or not split_line[0] == "snapshot":
                    raise IOError("Snapshot ID cannot be parsed. Error in \"%s\" file\n"
                                    "In line %s!" % (log_file.name, split_line))
                current_id = int(split_line[1].strip())
                snapshots[current_id] = {}
                continue

            if state is self.States.CONTENT:
                # Check if the line is part of the backtrace.
                # Every backtrace starts with something like "n0:".
                if re.match("^\s*n\d*:", line):
                    continue
                line = line.strip()
                split_line = line.split("=")
                if len(split_line) is not 2:
                    raise IOError("Error in parsing the \"%s\" file\n"
                                    "In line %s!" % (log_file.name, split_line))
                key = split_line[0]
                value = split_line[1]
                if value.isdigit():
                    snapshots[current_id][key] = int(value)
                else:
                    snapshots[current_id][key] = value
                continue

        if state is self.States.NONE:
            raise IOError("The format of the %s log file is not supported! Error in parsing!" % log_file.name)
        if state is self.States.ID:
            raise IOError("The last snapshot in %s file is not complete! Error in parsing!" % log_file.name)
        return snapshots

    def get_run_length(self):
        max_key = max(self.snapshots.keys())
        process_run_length = (float(self.snapshots[max_key]["timestamp"]) - self.snapshots[0]["timestamp"]) / 1000000
        return process_run_length

    def get_snapshot_per_sec(self):
        max_key = max(self.snapshots.keys())
        process_run_length = self.get_run_length()
        return max_key / process_run_length

    def get_snapshot(self, snapshot_id):
        max_key = max(self.snapshots.keys())
        if snapshot_id <= 0:
            return self.snapshots[0]
        elif snapshot_id >= max_key:
            return self.snapshots[max_key]
        return self.snapshots[snapshot_id]

    def get_snapshot_id(self, wanted_snapshot):
        for snapshot_id, snapshot in self.snapshots.items():
            if snapshot == wanted_snapshot:
                return snapshot_id
        return None

    def get_nearest_snapshots(self, base_snapshot):
        nearest_snapshot_id = None
        minimum_difference = sys.maxint
        nearest_snapshots = []
        if base_snapshot["timestamp"] < self.snapshots[0]["timestamp"]:
            return None
        for (snapshot_id, snapshot) in sorted(self.snapshots.items()):
            if snapshot_id is 0:
                continue

            current_difference = abs(base_snapshot["timestamp"] - snapshot["timestamp"])
            if current_difference < minimum_difference and current_difference < MAX_SNAPSHOT_DIFF:
                minimum_difference = current_difference
                nearest_snapshot_id = snapshot_id

        if nearest_snapshot_id is None:
            return None

        if nearest_snapshot_id is 1:
            nearest_snapshots.append(self.get_snapshot(nearest_snapshot_id))
            nearest_snapshots.append(self.get_snapshot(nearest_snapshot_id + 1))
        elif nearest_snapshot_id is max(self.snapshots.keys()):
            nearest_snapshots.append(self.get_snapshot(nearest_snapshot_id - 1))
            nearest_snapshots.append(self.get_snapshot(nearest_snapshot_id))
        else:
            nearest_snapshots.append(self.get_snapshot(nearest_snapshot_id - 1))
            nearest_snapshots.append(self.get_snapshot(nearest_snapshot_id))
            nearest_snapshots.append(self.get_snapshot(nearest_snapshot_id + 1))
        return nearest_snapshots

    def get_start_end_time(self):
        max_key = max(self.snapshots.keys())
        start = self.get_snapshots()[0]["timestamp"]
        end = self.get_snapshots()[max_key]["timestamp"]
        TimeInterval = collections.namedtuple("TimeInterval", ["start", "end"])
        time = TimeInterval(start, end)
        return time

    def __contains__(self, wanted_snapshot):
        for (snapshot_id, snapshot) in self.snapshots.items():
            if wanted_snapshot["timestamp"] == snapshot["timestamp"] and \
               wanted_snapshot["mem_heap_B"] == snapshot["mem_heap_B"]:
                return True
        return False

    def __str__(self):
        string = ""
        snapshots = self.get_snapshots()
        for (snapshot_id, snapshot) in snapshots.items():
            if snapshot_id is not max(snapshots.keys()):
                snapshot_string = "Timestamp: %d, Used memory: %d\n" % (snapshot["timestamp"], snapshot["mem_heap_B"])
            else:
                snapshot_string = "Timestamp: %d, Used memory: %d" % (snapshot["timestamp"], snapshot["mem_heap_B"])
            string += snapshot_string
        return string


class ResultGenerator(object):
    def __init__(self, output_list):
        self.parent_output = self._get_parent_output(output_list)
        self.children_output = self._get_children_output(output_list)
        self.snapshots_to_use = self._get_snapshots_to_use()
        self.useful_memories = self._calculate_useful_memories()
        self.extra_memories = self._calculate_extra_memories()
        self.found_nearest_snapshots_percentage = self._calculate_percentage()
        self.chosen_snapshots = self._get_snapshots_with_max_memory()

    def get_chosen_snapshots(self):
        return self.chosen_snapshots

    def get_parent_output(self):
        return self.parent_output

    def get_children_output(self):
        return self.children_output

    def _get_parent_output(self, output_list):
        maximum_difference = 0
        parent_output = None
        minimum_time = sys.maxint
        for massif_output in output_list:
            if massif_output.get_snapshots()[0]["timestamp"] < minimum_time:
                minimum_time = massif_output.get_snapshots()[0]["timestamp"]
                parent_output = massif_output
        """for massif_output in output_list:
            # TODO: check first timestamp
            process_run_length = massif_output.get_run_length()
            if process_run_length > maximum_difference:
                maximum_difference = process_run_length
                parent_output = massif_output"""
        return parent_output

    def _get_children_output(self, output_list):
        children_output = []
        for massif_output in output_list:
            if massif_output is not self.parent_output:
                children_output.append(massif_output)
        return children_output

    def _get_snapshots_with_max_memory(self):
        chosen_snapshots = []
        max_memory = 0
        for snapshot_vector in self.snapshots_to_use:
            used_memory = self._calculate_useful_memory(snapshot_vector) + self._calculate_extra_memory(snapshot_vector)
            if used_memory > max_memory:
                max_memory = used_memory
                del chosen_snapshots[:]
                for snapshot in snapshot_vector:
                    chosen_snapshots.append(snapshot)
        return chosen_snapshots

    def _calculate_useful_memory(self, snapshot_vector):
        used_memory = 0
        for snapshot in snapshot_vector:
            used_memory += snapshot["mem_heap_B"]
        return used_memory

    def _calculate_extra_memory(self, snapshot_vector):
        extra_memory = 0
        for snapshot in snapshot_vector:
            extra_memory += snapshot["mem_heap_extra_B"]
        return extra_memory

    def _calculate_useful_memories(self):
        useful_memories = []
        for snapshot_vector in self.snapshots_to_use:
            used_memory = 0
            for snapshot in snapshot_vector:
                used_memory += snapshot["mem_heap_B"]
            useful_memories.append(used_memory)
        return useful_memories

    def _calculate_extra_memories(self):
        extra_memories = []
        for snapshot_vector in self.snapshots_to_use:
            extra_memory = 0
            for snapshot in snapshot_vector:
                extra_memory += snapshot["mem_heap_extra_B"]
            extra_memories.append(extra_memory)
        return extra_memories

    def _calculate_percentage(self):

        match_counter = 0
        interval = self.get_min_max_of_interval()
        interval_len = interval.maximum_end - interval.minimum_start
        for snapshot_vector in range(interval.minimum_start, interval.maximum_end + 1):
            if len(self.snapshots_to_use[snapshot_vector]) is not 1:
                match_counter += 1
        percentage = match_counter / float(interval_len) * 100
        return percentage

    def _get_snapshots_to_use(self):
        max_key = max(self.parent_output.get_snapshots().keys())
        snapshots_to_use = []
        parent_snapshots = self.parent_output.get_snapshots()

        if len(self.children_output) is 0:
            for parent_snapshot in parent_snapshots.values():
                snapshots_to_use.append([parent_snapshot])
            return snapshots_to_use

        interval = self.get_min_max_of_interval()

        for snapshot_key in range(0, interval.minimum_start):
            snapshots_to_use.append([parent_snapshots[snapshot_key]])

        for parent_snapshot_key in range(interval.minimum_start, interval.maximum_end + 1):
            nearest_snapshots_per_files = {}
            for child_output in self.children_output:
                closer_snapshots = child_output.get_nearest_snapshots(parent_snapshots[parent_snapshot_key])
                if closer_snapshots is not None:
                    nearest_snapshots_per_files[child_output.get_file_name()] = closer_snapshots
            if len(nearest_snapshots_per_files) is not 0:
                nearest_snapshots = self._find_nearest_snapshots(parent_snapshots[parent_snapshot_key],
                                                                 nearest_snapshots_per_files)
                snapshots_to_use.append(nearest_snapshots)
                continue
            snapshots_to_use.append([parent_snapshots[parent_snapshot_key]])

        for snapshot_key in range(interval.maximum_end + 1, max_key + 1):
            snapshots_to_use.append([parent_snapshots[snapshot_key]])

        return snapshots_to_use

    def _find_nearest_snapshots(self, parent_snapshot, nearest_snapshots_per_files):
        lists = []
        lists.append([parent_snapshot])
        for file_name in nearest_snapshots_per_files:
            lists.append(nearest_snapshots_per_files[file_name])
        permutations = list(itertools.product(*lists))

        minimal_difference = sys.maxint
        nearest_snapshots = None
        for permutation in permutations:
            elapsed_time = self._check_difference_in_time(permutation)
            if elapsed_time < minimal_difference:
                minimal_difference = elapsed_time
                nearest_snapshots = permutation
        return nearest_snapshots

    def _check_difference_in_time(self, permutation):
        maximum_timestamp = 0
        minimum_timestamp = sys.maxint
        for snapshot in permutation:
            if snapshot["timestamp"] < minimum_timestamp:
                minimum_timestamp = snapshot["timestamp"]
            if snapshot["timestamp"] > maximum_timestamp:
                maximum_timestamp = snapshot["timestamp"]
        elapsed_time = maximum_timestamp - minimum_timestamp
        return elapsed_time

    def get_min_max_of_interval(self):
        time_intervals = self.get_covered_time()
        minimum_start = sys.maxint
        maximum_end = 0
        for file_interval in time_intervals:
            if time_intervals[file_interval][0] < minimum_start:
                minimum_start = time_intervals[file_interval][0]
            if time_intervals[file_interval][1] > maximum_end:
                maximum_end = time_intervals[file_interval][1]
        TimeInterval = collections.namedtuple("TimeInterval", ["minimum_start", "maximum_end"])
        time = TimeInterval(minimum_start, maximum_end)
        return time

    def get_covered_time(self):
        intervals_per_file = {}
        for output in self.children_output:
            minimum = None
            maximum = None
            start_end_time = output.get_start_end_time()
            for (snapshot_key, snapshot) in sorted(self.parent_output.get_snapshots().items()):
                if snapshot["timestamp"] >= start_end_time.start and minimum is None:
                    minimum = snapshot_key
                if snapshot["timestamp"] >= start_end_time.end and maximum is None:
                    maximum = snapshot_key
                    break
            if maximum is None:
                maximum = max(self.parent_output.get_snapshots())
            intervals_per_file[output.get_file_name()] = (minimum, maximum)
        return intervals_per_file

    def __str__(self):
        parent_process = self.parent_output.get_file_name()
        child_processes = ""
        for child in self.children_output:
            child_processes += child.get_file_name()
        string = "Maximum useful memory: %d Mib Maximum extra memory %d KiB\n" \
                 "Parent process: %s\n" \
                 "Child process(es): %s\n" \
                 "Snapshots found nearby: %f %%" \
                 % (self._calculate_useful_memory(self.chosen_snapshots)/TO_MEGA,
                    self._calculate_extra_memory(self.chosen_snapshots)/TO_KILO,
                    parent_process, child_processes, self.found_nearest_snapshots_percentage)
        return string


def print_result_verbosity_1(chosen_snapshots):
    maximum_memory = 0
    for snapshot in chosen_snapshots:
        maximum_memory += snapshot["mem_heap_B"]
    print("%d %.2f %.2f\n" % (maximum_memory, float(maximum_memory)/TO_KILO, float(maximum_memory)/TO_MEGA))


def print_result_verbosity_2(chosen_snapshots, output_list):
    print_result_verbosity_1(chosen_snapshots)
    for snapshot in chosen_snapshots:
        for output in output_list:
            if snapshot in output:
                snapshot_id = output.get_snapshot_id(snapshot)
                print("%s:\n"
                      " snapshot_id = %d\n"
                      " timestamp = %d\n"
                      " mem_heap_B = %d\n"
                      % (output.get_file_name(), snapshot_id, snapshot["timestamp"], snapshot["mem_heap_B"]))
                continue


"""def validate_output_files(output_list):
    start_time = sys.maxint
    end_time = 0
    run_length = 0
    for output in output_list:
        time = output.get_start_end_time()
        run = output.get_run_length()
        if run > run_length:
            run_length = run
        if time.start < start_time:
            start_time = time.start
        if time.end > end_time:
            end_time = time.end
    longest_time = (float(end_time) - start_time) / 1000000
    if not run_length <= longest_time + 1 or not run_length >= longest_time - 1:
        raise IOError("The log files are not from one measurement!")"""


def main():
    if not len(sys.argv) > 1:
        sys.stderr.write("No log files were provided!\n")
        exit(1)

    output_list = []
    try:
        for i in range(1, len(sys.argv)):
            file_name = sys.argv[i]
            output_list.append(MassifOutput(file_name))
        # validate_output_files(output_list)
        result_generator = ResultGenerator(output_list)
        chosen_snapshots = result_generator.get_chosen_snapshots()
        print_result_verbosity_1(chosen_snapshots)
    except IOError as err:
        sys.stderr.write("ERROR with the files: %s\n" % str(err))
        exit(1)
    except RuntimeError as err:
        sys.stderr.write("RuntimeError: %s\n" % str(err))
        exit(1)
    except Exception as err:
        sys.stderr.write("ERROR: %s\n" % str(err))
        exit(1)


if __name__ == "__main__":
    main()
