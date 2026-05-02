PROJECT_ID  ?= $(shell grep GCP_PROJECT .env 2>/dev/null | cut -d= -f2)
REGION      ?= us-west2
SERVICE     ?= huehunt
IMAGE       := wulfl/huehunt
PORT        ?= 8080

ifneq (,$(wildcard .env))
  include .env
  export
endif

export GOOGLE_APPLICATION_CREDENTIALS := $(CURDIR)/db-creds.json

_OAUTH_ID     := $(shell python3 -c "import json; d=json.load(open('oauth-creds.json')); print(d.get('web',d)['client_id'])" 2>/dev/null)
_OAUTH_SECRET := $(shell python3 -c "import json; d=json.load(open('oauth-creds.json')); print(d.get('web',d)['client_secret'])" 2>/dev/null)

.PHONY: install run build run-docker push deploy logs

install:
	pip install -r requirements.txt

run:
	python src/app.py --port $(PORT)

build:
	docker build -t $(IMAGE):latest .

run-docker: build
	docker run --rm -p $(PORT):$(PORT) \
	  -v "$(CURDIR)/db-creds.json:/app/db-creds.json:ro" \
	  -v "$(CURDIR)/oauth-creds.json:/app/oauth-creds.json:ro" \
	  -e SECRET_KEY=$(SECRET_KEY) \
	  -e GCS_BUCKET=$(GCS_BUCKET) \
	  -e GCP_PROJECT=$(GCP_PROJECT) \
	  -e GOOGLE_APPLICATION_CREDENTIALS=/app/db-creds.json \
	  $(IMAGE):latest

push: build
	docker push $(IMAGE):latest

deploy: push
	gcloud run deploy $(SERVICE) \
	  --image docker.io/$(IMAGE):latest \
	  --project $(GCP_PROJECT) \
	  --region $(REGION) \
	  --platform managed \
	  --allow-unauthenticated \
	  --service-account huehunt-runner@$(GCP_PROJECT).iam.gserviceaccount.com \
	  --set-env-vars "SECRET_KEY=$(SECRET_KEY),GCS_BUCKET=$(GCS_BUCKET),GOOGLE_CLIENT_ID=$(_OAUTH_ID),GOOGLE_CLIENT_SECRET=$(_OAUTH_SECRET)"

logs:
	gcloud run services logs tail $(SERVICE) --region $(REGION)
