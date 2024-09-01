#!/bin/bash

# check if pwd is in the right directory
if [ ! -f "update.sh" ]; then
  cd /home/leaps/leaps/src/leaps
fi
git pull
sudo supervisorctl restart leaps