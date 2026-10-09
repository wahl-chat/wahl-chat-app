terraform {
  # Remote state in GCS. Bucket is created by hand before the first `terraform init`
  # (Terraform can't bootstrap the bucket that holds its own state):
  #   gcloud storage buckets create gs://wahl-chat-dev-tfstate \
  #     --project=wahl-chat-dev --location=europe-west1 --uniform-bucket-level-access
  #   gcloud storage buckets update gs://wahl-chat-dev-tfstate --versioning
  backend "gcs" {
    bucket = "wahl-chat-dev-tfstate"
    prefix = "app"
  }
}
