#!/bin/bash

FILE=$1

gnuplot > $FILE.pdf  <<EOF
set style data linespoints
set terminal pdf
show timestamp
set xlabel "time (seconds)"
set ylabel "Segments (cwnd, ssthresh)"
plot "$FILE" using 1:7 title "snd_cwnd", \
    "$FILE" using 1:(\$8>=2147483647 ? 0 : \$8) title "snd_ssthresh"

EOF
