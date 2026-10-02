#!/bin/sh

# if grep -q "$1" "$2"
if grep -qiE "$1" "$2"
then
    echo "Pipeline ran successfully"
    `exit 0`
else
   echo "Failed to run pipeline ($1 failed)"
   `exit 1`
fi 

