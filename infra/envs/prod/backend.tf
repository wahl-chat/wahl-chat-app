terraform {
  # Remote state in GCS. Bucket created by hand before the first `terraform init`:
  #   gcloud storage buckets create gs://wahl-chat-tfstate \
  #     --project=wahl-chat --location=europe-west1 --uniform-bucket-level-access
  #   gcloud storage buckets update gs://wahl-chat-tfstate --versioning
  backend "gcs" {
    bucket = "wahl-chat-tfstate"
    prefix = "app"
  }
}
