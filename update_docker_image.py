"""
Docker Image Pull Script

This script pulls the ionutms/3d-model-server:latest Docker image.
It displays progress information during the pull operation
and handles potential errors that might occur.
"""

import docker


def pull_docker_image(image_name):
    """
    Pull a Docker image and display progress information.

    Args:
        image_name (str):
            The name of the Docker image to pull (including tag if specified)

    Returns:
        bool: True if successful, False otherwise
    """
    # Initialize the Docker client
    client = docker.from_env()

    print(f"Pulling Docker image: {image_name}")
    print(
        "This may take a while depending on your "
        "internet connection and the image size...\n"
    )

    try:
        # Pull the image with progress information
        for progress_line in client.api.pull(
            image_name, stream=True, decode=True
        ):
            # Process the progress information
            if "progress" in progress_line:
                status = progress_line.get("status", "")
                progress = progress_line.get("progress", "")
                id_info = progress_line.get("id", "")
                if id_info and progress:
                    print(f"\r{id_info}: {status} {progress}", end="")
            elif "status" in progress_line:
                print(f"\r{progress_line.get('status', '')}", end="")

        # Print a newline after progress is complete
        print("\n")

        # Verify the image was pulled successfully
        images = client.images.list()
        image_found = any(
            image_name in img.tags for img in images if img.tags
        )

        if image_found:
            print(f"Successfully pulled {image_name}")
            return True
        else:
            print(
                f"Warning: Cannot verify if {image_name} "
                "was pulled successfully."
            )
            return False

    except docker.errors.APIError as e:
        print(f"Error pulling Docker image: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False


if __name__ == "__main__":
    # The specific image to pull
    IMAGE_NAME = "ionutms/3d-model-server:latest"

    # Pull the Docker image
    pull_docker_image(IMAGE_NAME)
