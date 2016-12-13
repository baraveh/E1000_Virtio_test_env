from utils.shell_utils import run_command_check


class Graph:
    def __init__(self, x_label, y_label, output_filename, data_filename):
        self.titles = list()
        self.x_label = x_label
        self.y_label = y_label
        self.x_tics = ''
        self.log_scale_x = -1

        self.output_filename = output_filename
        self.data_filename = data_filename
        self.data_filename2 = ""
        self.script_filename = ""

        self.data = dict()

    def set_column_names(self, titles):
        self.titles = titles

    def add_data(self, title, x, value):
        assert title in self.titles
        if x not in self.data:
            self.data[x] = dict()

        if title not in self.data[x]:
            self.data[x][title] = value
        else:
            self.data[x][title] += value

    def set_x_tics(self, values, labels):
        assert(len(values) == len(labels))

        self.x_tics = "("
        for label, value in zip(values, labels):
            self.x_tics += r'\"{}\"{},'.format(label, value)

        self.x_tics += ")"

    def create_graph(self, retries):
        """
        write data to file
        run gnuplot
        """
        with open(self.data_filename, "w") as f:
            f.write("title ")
            for title in self.titles:
                f.write("{} ".format(title))
            f.write("\n")
            for x in self.data:
                f.write("{} ".format(x))
                for title in self.titles:
                    f.write("{} ".format(float(self.data[x][title])) / float(retries))
            f.write("\n")

        command = "gnuplot -e '" \
                  "output_filename='{output}; " \
                  "data_filename='{data}'; " \
                  "y_label='{y_label}'; " \
                  "x_label='{x_label}'; " \
                  "x_tics='{x_tics}'; " \
                  "'".format(
                        output=self.output_filename,
                        data=self.data_filename,
                        y_label=self.y_label,
                        x_label=self.x_label,
                        x_tics=self.x_tics,
                  )

        if self.log_scale_x > 0:
            command += "log_scale_x='{log}'; ".format(log=self.log_scale_x)

        run_command_check(command)
