NAME ?= runcellpose_omnipose_no_pretrained
TAG ?= 1.0.2
REPO ?= cellprofiler
IMG := $(REPO)/$(NAME):$(TAG)

.PHONEY: build
build:
	docker build -t $(IMG) .

.PHONY: run
run:
	docker run \
	-it --rm \
	$(IMG) \
	bash

.PHONY: deploy
deploy:
	docker image push $(IMG)

.PHONY: clean_docker
clean_docker:
	docker rmi $(IMG)
