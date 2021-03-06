import shutil
from operator import methodcaller
from statistics import mean, stdev
import itertools
import logging
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os.path
from collections import defaultdict

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
        self.dir_name = os.path.dirname(output_filename)
        self.graph_name = os.path.basename(output_filename)

        self.data = dict()
        self.x_tics_values = []
        self.x_tics_names = []
        self.normalize = normalize

    def set_column_names(self, titles):
        self.titles = titles

    def add_data(self, title, x, value, is_normalize=False):
        assert title in self.titles
        if not is_normalize:
            normalize = self.normalize
        else:
            normalize = 1

        if x not in self.data:
            self.data[x] = dict()

        if title not in self.data[x]:
            self.data[x][title] = [float(value)/normalize]
        else:
            self.data[x][title].append(float(value)/normalize)

    def set_x_tics(self, values, labels):
        assert(len(values) == len(labels))
        self.x_tics_values = values
        self.x_tics_names = labels

    def create_data_file(self, data=None, titles=None):
        raise NotImplementedError()

    def dump_to_json(self, data=None):
        if data is None:
            data = self.data

        with open(self.json_filename, "w") as f:
            json.dump(data, f)

    def _change_folder(self, folder):
        self.output_filename = os.path.join(folder, self.graph_name + ".pdf")
        self.data_filename = os.path.join(folder, self.graph_name + ".txt")
        self.json_filename = os.path.join(folder, self.graph_name + ".json")
        self.png_filename = os.path.join(folder, self.graph_name + ".png")
        self.commnad_file = os.path.join(folder, self.graph_name + ".command")
        self.dir_name = folder

    def _limit_data(self, titles_to_include):
        new_data = defaultdict(dict)

        for x in self.data:
            for title in titles_to_include:
                new_data[x][title] = self.data[x].get(title, 0)

        return new_data

    def create_graph(self, retries, titles_to_include=None, folder=None):
        # adjust file names
        if folder is not None:
            old_folder = self.dir_name
            self._change_folder(folder)

        # adjust data
        if titles_to_include is not None:
            data=self._limit_data(titles_to_include)
        else:
            data = self.data

        self._create_graph(retries, data=data, titles=titles_to_include)
        if folder is not None:
            self._change_folder(old_folder)

    def _create_graph(self, retries, data=None, titles=None):
        """
        write data to file
        run gnuplot
        :param titles:
        :param data:
        """
        self.create_data_file(data, titles)

        raise NotImplementedError()

    def convert2png(self):
        """
        convert pdf to png file
        """
        cmd = "convert -density 150 {pdf} -flatten -quality 90 {png}".format(pdf=self.output_filename,
                                                                     png=self.png_filename)
        run_command_check(cmd)

    def load_old_results(self, vm_name, filename=None):
        if filename is None:
            filename = self.json_filename

        try:
            with open(filename, "r") as f:
                old_json = json.load(f)

            for x in old_json:
                for data in old_json[x][vm_name]:
                    self.add_data(vm_name, float(x), data, is_normalize=True)
        except FileNotFoundError:
            for x in self.data:
                self.add_data(vm_name, int(x), 0)


class GraphGnuplot(GraphBase):
    def __init__(self, *args, **kargs):
        super(GraphGnuplot, self).__init__(*args, **kargs)
        self.script_filename = "gnuplot/plot_lines_message_size_ticks"
        assert isinstance(args[2], str)
        self.command_file = args[2] + ".command"
        # self.dir_name = os.path.dirname(self.output_filename)
        self._real_script_filename = ''

    def set_x_tics(self, values, labels):
        super(GraphGnuplot, self).set_x_tics(values, labels)

        labels_tics = [] 
        for label, value in zip(labels, values):
            labels_tics.append(r'\"{}\"{}'.format(label, value))

        self.x_tics = "({})".format(",".join(labels_tics))

    def create_data_file(self, data=None, titles=None):
        if data is None:
            data = self.data

        if titles is None:
            titles = self.titles

        with open(self.data_filename, "w") as f:
            f.write("title ")
            for title in titles:
                f.write("{} ".format(title))
            f.write("\n")
            for x in sorted(data, key=int):
                f.write("{} ".format(x))
                for title in titles:
                    try:
                        f.write("{} ".format(mean((a for a in data[x][title]))))
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
PLOT:=$(shell awk 'NF>1{print $$NF}' ${COMMANDS} | sort|uniq )

all: $(PDFS) $(PNGS)
\t@#-find -name '*.command' | xargs -l bash -x
\t@#-find -name '*.pdf' | xargs -I {} bash -x -c "export F={} && convert -density 150 \$${F} -flatten -quality 90 \$${F%pdf}png"

%.png: %.pdf
\tconvert -density 150 $^ -flatten -quality 90 $@

%.pdf: %.command $(PLOT)
\t@cat ./$*.command
\tbash ./$*.command

clean:
\trm -f *.pdf *.png
                """)

    def _calc_additional_params(self, data=None, titles=None):
        return ''

    def _create_graph(self, retries, data=None, titles=None):
        """
        write data to file
        run gnuplot
        :param titles:
        :param data:
        """
        self.create_data_file(data, titles)
        self.dump_to_json(data)
        self.copy_cmd_file()
        self.create_makefile()

        addition = self._calc_additional_params(data, titles)
        if self.log_scale_x > 1:
            addition += "log_scale_x='{log}'; ".format(log=self.log_scale_x)
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
        with open(os.path.join(self.dir_name, self.graph_name + ".command"), "w") as f:
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

    def _create_graph(self, retries, data=None, titles=None):
        if data is None:
            data = self.data

        if titles is None:
            titles = self.titles

        self.create_data_file(data, titles)
        self.dump_to_json(data)

        if self.log_scale_x:
            plt.xscale("log", basex=self.log_scale_x)
        for title in titles:
            self._plot_by_title(title)

        plt.xlabel(self.x_label)
        plt.ylabel(self.y_label)
        if self.x_tics_names:
            plt.xticks(self.x_tics_values, self.x_tics_names, rotation=45)
        else:
            plt.xticks([x for x in data])
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

    def create_data_file(self, data=None, titles=None):
        if data is None:
            data = self.data

        if titles is None:
            titles = self.title

        with open(self.data_filename, "w") as f:
            f.write("title ")
            for title in titles:
                f.write("{} {}_min {}_max ".format(title, title, title))
            f.write("\n")
            for x in sorted(data):
                f.write("{} ".format(x))
                for title in titles:
                    f.write("{mean} {min} {max} ".format(
                        mean=mean(data[x][title]),
                        min=min(data[x][title]),
                        max=max(data[x][title])
                    ))
                f.write("\n")


# set the default graph class
Graph = GraphGnuplot


class MultipleGraphs(Graph):
    def __init__(self, graph1: GraphBase, graph2: GraphBase, *args, **kargs):
        super().__init__(*args, **kargs)
        self.graph1 = graph1
        self.graph2 = graph2

    def _calc_data(self):
        raise NotImplementedError()

    def _create_graph(self, *args, **kargs):
        self._calc_data()
        super()._create_graph(*args, **kargs)


class RatioGraph(MultipleGraphs):
    """
    create graph with ratio between two different graphs
    """
    def _calc_data(self):
        for x in self.graph1.data.keys():
            for title in self.graph1.data[x].keys():
                for val1, val2 in zip(self.graph1.data[x][title], self.graph2.data[x][title]):
                    if val2 != 0:
                        self.add_data(title, x, val1 / val2)
                    else:
                        self.add_data(title, x, 0)


class SameDataGraph(Graph):
    def __init__(self, graph1: GraphBase, *args, **kargs):
        super().__init__(*args, **kargs)
        self._graph1 = graph1
        self.data_filename = graph1.data_filename
        self.json_filename = graph1.json_filename

    def dump_to_json(self, data=None):
        pass

    def create_data_file(self, data=None, titles=None):
        pass

    def _change_folder(self, folder):
        super()._change_folder(folder)
        self.data_filename = os.path.join(folder, self._graph1.graph_name + ".txt")
        self.json_filename = os.path.join(folder, self._graph1.graph_name + ".json")


class GraphRatioGnuplot(SameDataGraph):
    def __init__(self, *args, **kargs):
        super().__init__(*args, **kargs)
        self.script_filename = "gnuplot/plot_lines_message_size_ticks_ratio"
        self.log_scale_y = 2


class GraphScatter(MultipleGraphs):
    # TODO: update to use subset of data
    def __init__(self, *args, **kargs):
        super().__init__(*args, **kargs)
        self.script_filename = "gnuplot/plot_scatter"
        self._scatter_data = dict()  # different from data, dict[title] = list(x,y)

    def add_data(self, title, x, value):
        super().add_data(title, x, value)
        if title not in self._scatter_data:
            self._scatter_data[title] = list()
        self._scatter_data[title].append((x,value))

    def _calc_data(self):
        for x in self.graph1.data.keys():
            for title in self.graph1.data[x].keys():
                for val1, val2 in zip(self.graph1.data[x][title], self.graph2.data[x][title]):
                    self.add_data(title, val1, val2)

    def create_data_file(self, data=None, titles=None):
        if titles is None:
            titles = self.titles

        with open(self.data_filename, "w") as f:
            for title in titles:
                f.write("title {}\n".format(title))
                for x, y in self._scatter_data[title]:
                    f.write("{} {}\n".format(x, y))
                f.write("\n\n")

    def _calc_additional_params(self, data=None, titles=None):
        if titles is None:
            titles = self.titles

        return "blocks_num='{blocks}'; ".format(blocks=len(titles))


class EmptyGraph(Graph):
    def __init__(self, *args, **kargs):
        self.data = defaultdict(lambda: defaultdict(lambda: list()))


class FuncGraph(MultipleGraphs):
    def __init__(self, func, *args, more_graphs=None, **kargs):
        super().__init__(*args, **kargs)
        self._func = func

        if more_graphs is None:
            more_graphs = tuple()
        self._more_graphs = more_graphs

    def _calc_data(self):
        for x in self.graph1.data.keys():
            for title in self.graph1.data[x].keys():
                graphs_data = [g.data[x][title] for g in (self.graph1, self.graph2) + self._more_graphs if not isinstance(g, EmptyGraph)]
                for value in zip(*graphs_data):
                    self.add_data(title, x, self._func(*value))


if __name__ == "__main__":
    pass
