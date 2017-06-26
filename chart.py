#!/usr/bin/env python

import sys
import os
import re
import plotly
from plotly.graph_objs import Scatter, Bar, Layout


def main():
    dir_name = sys.argv[1]
    files_per_version = {}

    for root, dirs, filenames in os.walk(dir_name):
        if re.match("\./$", root):
            continue
        files_per_version[root] = []
        for filename in filenames:
            files_per_version[root].append(filename)
    first_root = files_per_version.keys()[0]
    first_files = files_per_version.get(first_root)

    for file_name in first_files:
        data_lines = []
        data_bars = []
        webkit_mem = None
        webkit_results = []
        webengine_results = []
        versions = []
        measured_site = None
        exists_in_every_version = True
        for root, files in files_per_version.items():
            if file_name not in files:
                exists_in_every_version = False
        if not exists_in_every_version:
            continue
        for root in files_per_version.keys():
            file_to_open = os.path.join(root, file_name)
            measure = open(file_to_open, "r")
            split_name = file_to_open.split("/")
            engine = None
            site = None
            version = None
            for part in split_name:
                if re.match(".*QtWebkit.*", part):
                    engine = part
                if re.match(".*QtWebEngine.*", part):
                    name_and_version = part.split("-")
                    engine = name_and_version[0]
                    version = name_and_version[1]
                if re.match(".*\.txt", part):
                    site = part.split(".")[0]
            memories = []
            x_coords = []
            i = 0
            if measured_site is None:
                measured_site = site
            if not measured_site == site:
                sys.stderr.write("Error\n")
                exit(1)
            for line in measure:
                split_line = line.split()
                if not len(split_line) == 0:
                    i += 1
                    memories.append(float(split_line[2]))
                    x_coords.append(i)
            mem = memories
            mem.remove(max(mem))
            mem.remove(min(mem))
            average_memory = sum(mem) / len(mem)

            if engine == "QtWebEngine":
                versions.append("{}".format(version))
                webengine_results.append(average_memory)
            elif engine == "QtWebkit":
                webkit_mem = average_memory
        for i in range(0, len(versions)):
            webkit_results.append(webkit_mem)

        data_lines.append(Scatter(x=versions,
                                  y=webengine_results,
                                  name="QtWebEngine"))
        data_lines.append(Scatter(x=versions,
                                  y=webkit_results,
                                  name="QtWebkit"))
        plotly.offline.plot({
            "data": data_lines,
            "layout": Layout(title=measured_site,
                             xaxis=dict(title="Version"),
                             yaxis=dict(title="Memory consumption (MiB)"))
        },
            filename=measured_site + "-lines.html",
            image="jpeg",
            image_filename=measured_site + "-lines.jpeg"
        )

        data_bars.append(Bar(x=versions,
                             y=webengine_results,
                             name="QtWebEngine",
                             marker=dict(
                                 color='rgb(49,130,189)'
                             )))
        data_bars.append(Bar(x=versions,
                             y=webkit_results,
                             name="QtWebkit",
                             marker=dict(
                                 color='rgb(204,204,204)',
                             )))
        plotly.offline.plot({
            "data": data_bars,
            "layout": Layout(title=measured_site,
                             xaxis=dict(title="Version"),
                             yaxis=dict(title="Memory consumption (MiB)"),
                             barmode="group")
        },
            filename=measured_site + "-bars.html",
            image="jpeg",
            image_filename=measured_site + "-bars.jpeg"
        )


if __name__ == "__main__":
    main()
