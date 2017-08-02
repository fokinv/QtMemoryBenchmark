#!/bin/bash

function measure {
	FILEPATH=$1
	if [[ $FILEPATH == */index.html && $FILEPATH == */bootstrap/* ]]; then
		SITE=${FILEPATH%/index.html}
		SITE='bootstrap-'${SITE##*/}
	elif [[ $FILEPATH == */index.html && $FILEPATH == */html5/* ]]; then
		SITE=${FILEPATH%/index.html}
		SITE=${SITE##*/}
	elif [[ $FILEPATH  == *.html ]]; then
		SITE=${FILEPATH##*/}
		SITE=${SITE%%.*}
	else
		SITE=${FILEPATH#*.}
		SITE=${SITE%%.*}
	fi
	
	if [ ! -d "$SITE" ]; then
		mkdir $SITE
	fi

	for i in {1..10}; do
				~/Work/Freya/inst/bin/valgrind --tool=massif \
									   		 --trace-children=yes \
									   		 --time-unit=ms \
											 --smc-check=all-non-file \
											 --max-snapshots=1000 \
										   	 --detailed-freq=1000000 \
											 --depth=1 \
											 --massif-out-file="$SITE/$i-.out%p" \
											 ./Minimal ${FILEPATH}
				if [[ $? -ne 0 ]]; then
				    i = i - 1
				    echo "Error occurred in measure number: " $i "Error code: " $? >> $SITE.txt
				else
				    ~/Work/Qt/MemoryScript/parse-logs.py $SITE/$i-* >> $SITE.txt
				fi
	done
}


for ARG in $*; do
	REGEX='(https?|ftp|file)?(://)?[-A-Za-z0-9\+&@#/%?=~_|!:,.;]*[-A-Za-z0-9\+&@#/%=~_|]'
	if [ -d "$ARG" ]; then
		for LINE in $(find $ARG); do
			if [[ $LINE == */index.html || $LINE == */empty.html ]]; then
				measure $LINE
			fi
		done
	elif [[ $ARG =~ $REGEX ]]; then
		measure $ARG
	fi
done
