#! /bin/sh -x

NAME=amqpclt

./bin/${NAME} --pod > man/${NAME}.pod

pod2man --section=1 --center="${NAME} man page" --release="" man/${NAME}.pod > man/${NAME}.1

./bin/${NAME} --rst > docs/index.rst

