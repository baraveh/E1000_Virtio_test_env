from statistics import mean, stdev
import itertools
import logging
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from utils.shell_utils import run_command_check

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class GraphBase:
    def __init__(self, x_label, y_label, output_filename, data_filename):
        self.titles = list()
        self.x_label = x_label
        self.y_label = y_label
        self.x_tics = ''
        self.log_scale_x = 2

        self.output_filename = output_filename
        self.data_filename = data_filename
        self.data_filename2 = ""

        self.data = dict()
        self.x_tics_values = []
        self.x_tics_names = []

    def set_column_names(self, titles):
        self.titles = titles

    def add_data(self, title, x, value):
        assert title in self.titles
        if x not in self.data:
            self.data[x] = dict()

        if title not in self.data[x]:
            self.data[x][title] = [float(value)]
        else:
            self.data[x][title].append(float(value))

    def set_x_tics(self, values, labels):
        assert(len(values) == len(labels))
        self.x_tics_values = values
        self.x_tics_names = labels

    def create_data_file(self):
        with open(self.data_filename, "w") as f:
            f.write("title ")
            for title in self.titles:
                f.write("{} ".format(title))
            f.write("\n")
            for x in sorted(self.data):
                f.write("{} ".format(x))
                for title in self.titles:
                    f.write("{} ".format(mean(self.data[x][title])))
                f.write("\n")

    def dump_to_json(self):
        with open(self.data_filename + ".json", "w") as f:
            json.dump(self.data, f)

    def create_graph(self, retries):
        """
        write data to file
        run gnuplot
        """
        self.create_data_file()

        raise NotImplementedError()


class GraphGnuplot(GraphBase):
    def __init__(self, *args, **kargs):
        super(GraphGnuplot, self).__init__(*args, **kargs)
        self.script_filename = "gnuplot/plot_lines_message_size_ticks"

    def set_x_tics(self, values, labels):
        super(GraphGnuplot, self).set_x_tics(values, labels)

        labels_tics = [] 
        for label, value in zip(labels, values):
            labels_tics.append(r'\"{}\"{}'.format(label, value))

        #self.x_tics = "("
        #self.x_tics += ")"
        self.x_tics = "({})".format(",".join(labels_tics))

    def create_graph(self, retries):
        """
        write data to file
        run gnuplot
        """
        self.create_data_file()
        self.dump_to_json()

        addition = ""
        if self.log_scale_x > 0:
            addition = "log_scale_x='{log}'; ".format(log=self.log_scale_x)

        command = "gnuplot -e \"" \
                  "output_filename='{output}'; " \
                  "data_filename='{data}'; " \
                  "data_filename2=''; " \
                  "y_label='{y_label}'; " \
                  "x_label='{x_label}'; " \
                  "x_tics='{x_tics}'; " \
                  "{addition}" \
                  "\" " \
                  "{script}" \
                  "".format(
                        output=self.output_filename,
                        data=self.data_filename,
                        y_label=self.y_label,
                        x_label=self.x_label,
                        x_tics=self.x_tics,
                        addition=addition,
                        script=self.script_filename
                  )

        run_command_check(command)


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

# set the default graph class
Graph = GraphGnuplot

if __name__ == "__main__":
    pass
