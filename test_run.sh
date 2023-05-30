#!/bin/sh

# if grep -q "$1" "$2"
if grep -qiE "$1" "$2"
then
   echo "Failed to load plugin"
   `exit 1`
else
    echo "Pipeline ran successfully"
    `exit 0`
fi 

