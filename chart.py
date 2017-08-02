#!/usr/bin/env python

import sys
import os
import re
import plotly
from plotly.graph_objs import Scatter, Bar, Box, Layout, Data
from plotly.figure_factory import create_table


class MeasureResult(object):
    def __init__(self, gpu, engine, version, result, memories):
        self.gpu = gpu
        self.engine = engine
        self.version = version
        self.result = result
        self.memories = memories

    def get_gpu(self):
        return self.gpu

    def get_engine(self):
        return self.engine

    def get_version(self):
        return self.version

    def get_result(self):
        return self.result

    def get_memories(self):
        return self.memories

    def is_webengine(self):
        if self.engine == "QtWebEngine":
            return True
        return False

    def is_compare(self):
        if self.gpu is None:
            return False
        return True


def get_benchmark_list(dir_name):
    files_per_version = {}
    for root, dirs, filenames in os.walk(dir_name):
        if re.match("\./$", root):
            continue
        files_per_version[root] = []
        for filename in filenames:
            files_per_version[root].append(filename)
    return files_per_version


def is_measured_with_every_version(file_name, file_vectors):
    exists_in_every_version = True
    for files in file_vectors:
        if file_name not in files:
            exists_in_every_version = False
    return exists_in_every_version


def plot_bars(data_bars, measured_site, prefix):
    plotly.offline.plot({
        "data": data_bars,
        "layout": Layout(title=measured_site,
                         xaxis=dict(title="Version"),
                         yaxis=dict(title="Memory consumption (MiB)"),
                         barmode="group",
                         )
    },
        filename=prefix + measured_site + "-bars.html",
        image="jpeg",
        image_filename=prefix + measured_site + "-bars"
    )


def plot_lines(data_lines, measured_site):
    plotly.offline.plot({
        "data": data_lines,
        "layout": Layout(title=measured_site,
                         xaxis=dict(title="Version"),
                         yaxis=dict(title="Memory consumption (MiB)"),
                         )
    },
        filename=measured_site + "-lines.html",
        image="jpeg",
        image_filename=measured_site + "-lines"
    )


def plot_box(data_box, measured_site, table_rows):
    figure = create_table(table_rows)

    figure['data'].extend(Data(data_box))
    figure.layout.yaxis.update({'domain': [0, .42]})
    figure.layout.xaxis.update({'domain': [0, 2]})
    figure.layout.yaxis2.update({'domain': [.6, 1]})
    figure.layout.yaxis2.update({'anchor': 'x2'})
    figure.layout.xaxis2.update({'anchor': 'y2'})
    figure.layout.yaxis2.update({'title': 'Memory consumption (MiB)'})
    figure.layout.margin.update({'t': 75, 'l': 50})
    figure.layout.update({'title': measured_site})
    figure.layout.update({'height': 800})

    plotly.offline.plot(figure,
                        filename=measured_site + "-box-plot.html",
                        image="jpeg",
                        image_filename=measured_site + "-box-plot"
                        )


def append_bars_and_lines(data1, data2, data3, measure_results, table_rows):
    is_compare = measure_results[0].is_compare()
    results = {}
    versions = []
    webengine_compare = {}
    webkit_compare = {}
    webkit_labels = []
    for result in sorted(measure_results):
        if not is_compare:
            one_table_row = []
            if result.is_webengine():
                if result.get_engine() not in results:
                    results[result.get_engine()] = {}
                versions.append(result.get_version())
                results[result.get_engine()][result.get_version()] = result.get_result()
                full_name = result.get_engine() + "-" + result.get_version()
                one_table_row.append(result.get_version())
            else:
                if re.match(".*QtWebkit-Annulen.*", result.get_engine()):
                    one_table_row.append("WK-A")
                else:
                    one_table_row.append("WK")
                if result.get_engine() not in results:
                    results[result.get_engine()] = []
                for i in range(0, 5):
                    results[result.get_engine()].append(result.get_result())
                full_name = result.get_engine()
            memories = result.get_memories()
            for memory in memories:
                one_table_row.append(memory)
            table_rows.append(one_table_row)
            data3.append(Box(y=memories,
                             name=full_name,
                             xaxis='x2',
                             yaxis='y2'))
        else:
            if result.is_webengine():
                if result.get_gpu() not in webengine_compare:
                    webengine_compare[result.get_gpu()] = {}
                if not result.get_version() in versions:
                    versions.append(result.get_version())
                webengine_compare[result.get_gpu()][result.get_version()] = result.get_result()
            else:
                if result.get_gpu() not in webkit_compare:
                    webkit_compare[result.get_gpu()] = {}
                webkit_compare[result.get_gpu()][result.get_engine()] = result.get_result()
    versions = sorted(versions)
    if not is_compare:
        for key, values in sorted(results.items()):
            values_to_append = []
            if key == "QtWebEngine":
                for inner_key, inner_value in sorted(values.items()):
                    values_to_append.append(inner_value)
            else:
                values_to_append = values
            data2.append(Scatter(x=versions,
                                 y=values_to_append,
                                 mode='lines+markers+text',
                                 name=key,
                                 text=values_to_append,
                                 textposition='top'))
            data1.append(Bar(x=versions,
                             y=values_to_append,
                             name=key,
                             text=values_to_append,
                             textposition='auto'))
    else:
        for key, values in webengine_compare.items():
            values_to_append = []
            for inner_key, inner_value in sorted(values.items()):
                values_to_append.append(inner_value)
            data1.append(Bar(x=versions,
                             y=values_to_append,
                             name=key,
                             text=values_to_append,
                             textposition='auto'))
        for key, values in sorted(webkit_compare.items()):
            values_to_append = []
            for inner_key, inner_value in sorted(values.items()):
                webkit_labels.append(inner_key)
                values_to_append.append(inner_value)
            data2.append(Bar(x=webkit_labels,
                             y=values_to_append,
                             name=key,
                             text=values_to_append,
                             textposition='auto'))


def main():
    dir_name = sys.argv[1]
    files_per_version = get_benchmark_list(dir_name)

    first_root = files_per_version.keys()[0]
    first_files = files_per_version.get(first_root)

    for file_name in first_files:
        if not is_measured_with_every_version(file_name, files_per_version.values()):
            continue

        data_lines_or_bars = []
        data_bars = []
        data_box = []
        table_rows = [["Version", "Run1", "Run2", "Run3", "Run4", "Run5", "Run6", "Run7", "Run8"]]

        measure_results = []
        measured_site = None

        for root in sorted(files_per_version.keys()):
            amount_of_errors = 0
            file_to_open = os.path.join(root, file_name)
            gpu = None
            measure = open(file_to_open, "r")
            split_name = file_to_open.split("/")
            engine = None
            site = None
            version = None
            for part in split_name:
                if re.match(".*QtWebkit.*", part):
                    name_and_version = part.split("-")
                    if name_and_version[0] == "Intel" or name_and_version[0] == "Nvidia":
                        gpu = name_and_version[0]
                        engine = name_and_version[1]
                        if len(name_and_version) is 3:
                            engine += "-" + name_and_version[2]
                    else:
                        engine = part
                if re.match(".*QtWebEngine.*", part):
                    name_and_version = part.split("-")
                    if name_and_version[0] == "Intel" or name_and_version[0] == "Nvidia":
                        gpu = name_and_version[0]
                        engine = name_and_version[1]
                        version = name_and_version[2]
                    else:
                        engine = name_and_version[0]
                        version = name_and_version[1]
                if re.match(".*\.txt", part):
                    site = part.split(".")[0]
            memories = []
            if measured_site is None:
                measured_site = site
            if not measured_site == site:
                sys.stderr.write("Error\n")
                exit(1)
            for line in measure:
                if re.match(".*Error.*", line):
                    amount_of_errors += 1
                    continue
                split_line = line.split()
                if len(split_line) is 0:
                    continue
                memories.append(float(split_line[2]))
            memory_values = memories
            if len(memory_values) > 2:
                memory_values.remove(max(memory_values))
                memory_values.remove(min(memory_values))
            mem_len = len(memory_values)
            average_memory = float(format((sum(memory_values) / mem_len), '.3f'))
            measure_results.append(MeasureResult(gpu, engine, version, average_memory, memory_values))
            measure.close()

        is_compare = measure_results[0].is_compare()
        append_bars_and_lines(data_bars, data_lines_or_bars, data_box, measure_results, table_rows)
        if is_compare:
            plot_bars(data_bars, measured_site, "WE-")
            plot_bars(data_lines_or_bars, measured_site, "WK-")
        else:
            plot_bars(data_bars, measured_site, None)
            plot_lines(data_lines_or_bars, measured_site)
            plot_box(data_box, measured_site, table_rows)


if __name__ == "__main__":
    main()
