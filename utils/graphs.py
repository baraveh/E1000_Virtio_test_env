import shutil
from statistics import mean, stdev
import itertools
import logging
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os.path

from utils.shell_utils import run_command_check, run_command

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class GraphBase:
    def __init__(self, x_label, y_label, output_filename: str, graph_title="",
                 normalize=1):
        self.titles = list()
        self.x_label = x_label
        self.y_label = y_label
        self.x_tics = ''
        self.log_scale_x = 2
        self.log_scale_y = 1
        self.graph_title = graph_title

        self.output_filename = output_filename + ".pdf"
        self.data_filename = output_filename + ".txt"
        self.json_filename = output_filename + ".json"
        self.png_filename = output_filename + ".png"
        self.data_filename2 = ""

        self.data = dict()
        self.x_tics_values = []
        self.x_tics_names = []
        self.normalize = normalize

    def set_column_names(self, titles):
        self.titles = titles

    def add_data(self, title, x, value):
        assert title in self.titles
        if x not in self.data:
            self.data[x] = dict()

        if title not in self.data[x]:
            self.data[x][title] = [float(value)/self.normalize]
        else:
            self.data[x][title].append(float(value)/self.normalize)

    def set_x_tics(self, values, labels):
        assert(len(values) == len(labels))
        self.x_tics_values = values
        self.x_tics_names = labels

    def create_data_file(self):
        raise NotImplementedError()

    def dump_to_json(self):
        with open(self.json_filename, "w") as f:
            json.dump(self.data, f)

    def create_graph(self, retries):
        """
        write data to file
        run gnuplot
        """
        self.create_data_file()

        raise NotImplementedError()

    def convert2png(self):
        """
        convert pdf to png file
        """
        cmd = "convert -density 150 {pdf} -flatten -quality 90 {png}".format(pdf=self.output_filename,
                                                                     png=self.png_filename)
        run_command_check(cmd)


class GraphGnuplot(GraphBase):
    def __init__(self, *args, **kargs):
        super(GraphGnuplot, self).__init__(*args, **kargs)
        self.script_filename = "gnuplot/plot_lines_message_size_ticks"
        assert isinstance(args[2], str)
        self.command_file = args[2] + ".command"
        self.dir_name = os.path.dirname(self.output_filename)
        self._real_script_filename = ''

    def set_x_tics(self, values, labels):
        super(GraphGnuplot, self).set_x_tics(values, labels)

        labels_tics = [] 
        for label, value in zip(labels, values):
            labels_tics.append(r'\"{}\"{}'.format(label, value))

        self.x_tics = "({})".format(",".join(labels_tics))

    def create_data_file(self):
        with open(self.data_filename, "w") as f:
            f.write("title ")
            for title in self.titles:
                f.write("{} ".format(title))
            f.write("\n")
            for x in sorted(self.data):
                f.write("{} ".format(x))
                for title in self.titles:
                    try:
                        f.write("{} ".format(mean((a for a in self.data[x][title]))))
                    except KeyError:
                        f.write("0 ")
                f.write("\n")

    def copy_cmd_file(self):
        self._real_script_filename = os.path.basename(self.script_filename)
        shutil.copyfile(self.script_filename,
                        os.path.join(self.dir_name, self._real_script_filename))

    def create_makefile(self):
        makefile_path = os.path.join(self.dir_name, "Makefile")
        if not os.path.exists(makefile_path):
            with open(makefile_path, "w") as f:
                f.write("""
COMMANDS:=$(wildcard *.command)
PDFS:=$(patsubst %.command,%.pdf,$(COMMANDS))
PNGS:=$(patsubst %.command,%.png,$(COMMANDS))

all: $(PDFS) $(PNGS)
\t@#-find -name '*.command' | xargs -l bash -x
\t@#-find -name '*.pdf' | xargs -I {} bash -x -c "export F={} && convert -density 150 \$${F} -flatten -quality 90 \$${F%pdf}png"

%.png: %.pdf
\tconvert -density 150 $^ -flatten -quality 90 $@

%.pdf: %.command
\t@cat ./$*.command
\tbash ./$*.command

                """)

    def create_graph(self, retries):
        """
        write data to file
        run gnuplot
        """
        self.create_data_file()
        self.dump_to_json()
        self.copy_cmd_file()
        self.create_makefile()

        addition = ""
        if self.log_scale_x > 1:
            addition = "log_scale_x='{log}'; ".format(log=self.log_scale_x)
        if self.log_scale_y > 1:
            addition += "log_scale_y='{log}'; ".format(log=self.log_scale_y)

        command = "gnuplot -e \"" \
                  "output_filename='{output}'; " \
                  "data_filename='{data}'; " \
                  "data_filename2=''; " \
                  "graph_title='{graph_title}';" \
                  "y_label='{y_label}'; " \
                  "x_label='{x_label}'; " \
                  "x_tics='{x_tics}'; " \
                  "{addition}" \
                  "\" " \
                  "{script}" \
                  "".format(
                        output=os.path.basename(self.output_filename),
                        data=os.path.basename(self.data_filename),
                        graph_title=self.graph_title,
                        y_label=self.y_label,
                        x_label=self.x_label,
                        x_tics=self.x_tics,
                        addition=addition,
                        script=os.path.basename(self.script_filename)
                  )
        with open(self.command_file, "w") as f:
            f.write(command)
            f.write("\n")
        run_command_check(command, cwd=self.dir_name)
        self.convert2png()


class GraphMatplotlib(GraphBase):
    markers = itertools.cycle(['v', '^', '+', 'h', '.', 'o', '*'])

    def _plot_by_title(self, title):
        plt.plot(
            [x for x in sorted(self.data)],
            [mean(self.data[x][title]) for x in sorted(self.data)],
            label=title,
            marker=next(self.markers),
        )

    def create_graph(self, retries):
        self.create_data_file()
        self.dump_to_json()

        if self.log_scale_x:
            plt.xscale("log", basex=self.log_scale_x)
        for title in self.titles:
            self._plot_by_title(title)

        plt.xlabel(self.x_label)
        plt.ylabel(self.y_label)
        if self.x_tics_names:
            plt.xticks(self.x_tics_values, self.x_tics_names, rotation=45)
        else:
            plt.xticks([x for x in self.data])
        plt.grid(True, color='0.2')
        plt.legend(fancybox=True, framealpha=0.5)
        # lgd = plt.legend(bbox_to_anchor=(0., 1.02, 1., .102), loc=3,
        #                  ncol=2, mode="expand", borderaxespad=0.)
        plt.savefig(self.output_filename) #, bbox_extra_artists=(lgd,), bbox_inches='tight')


class GraphErrorBars(GraphMatplotlib):
    def _plot_by_title(self, title):
        plt.errorbar(
            [x for x in sorted(self.data)],
            [mean(self.data[x][title]) for x in sorted(self.data)],
            yerr=[stdev(self.data[x][title]) for x in sorted(self.data)],
            label=title,
            marker=next(self.markers),
        )
        logger.debug("%s:\n\tvalues:%s \n\tmean:%s, \n\tsd:%s", title,
                     [self.data[x][title] for x in sorted(self.data)],
                     [mean(self.data[x][title]) for x in sorted(self.data)],
                     [stdev(self.data[x][title]) for x in sorted(self.data)],
                     )


class GraphErrorBarsGnuplot(GraphGnuplot):
    def __init__(self, *args, **kargs):
        super(GraphErrorBarsGnuplot, self).__init__(*args, **kargs)
        self.script_filename = "gnuplot/plot_lines_error_bars"

    def create_data_file(self):
        with open(self.data_filename, "w") as f:
            f.write("title ")
            for title in self.titles:
                f.write("{} {}_min {}_max ".format(title, title, title))
            f.write("\n")
            for x in sorted(self.data):
                f.write("{} ".format(x))
                for title in self.titles:
                    f.write("{mean} {min} {max} ".format(
                        mean=mean(self.data[x][title]),
                        min=min(self.data[x][title]),
                        max=max(self.data[x][title])
                    ))
                f.write("\n")


# set the default graph class
Graph = GraphGnuplot


class RatioGraph(Graph):
    """
    create graph with ratio between two different graphs
    """
    def __init__(self, graph1: GraphBase, graph2: GraphBase, *args, **kargs):
        super(RatioGraph, self).__init__(*args, **kargs)
        self.graph1 = graph1
        self.graph2 = graph2

    def _calc_data(self):
        for x in self.graph1.data.keys():
            for title in self.graph1.data[x].keys():
                for val1, val2 in zip(self.graph1.data[x][title], self.graph2.data[x][title]):
                    self.add_data(title, x, val1 / val2)

    def create_graph(self, retries):
        self._calc_data()
        super(RatioGraph, self).create_graph(retries)


class SameDataGraph(Graph):
    def __init__(self, graph1: GraphBase, *args, **kargs):
        super().__init__(*args, **kargs)
        self.data_filename = graph1.data_filename
        self.json_filename = graph1.json_filename

    def dump_to_json(self):
        pass

    def create_data_file(self):
        pass


class GraphRatioGnuplot(SameDataGraph):
    def __init__(self, *args, **kargs):
        super().__init__(*args, **kargs)
        self.script_filename = "gnuplot/plot_lines_message_size_ticks_ratio"


if __name__ == "__main__":
    pass
