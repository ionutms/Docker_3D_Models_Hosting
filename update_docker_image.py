"""
Docker Image Pull and Extract Script

This script:
1. Pulls the ionutms/3d-model-server:latest Docker image
2. Extracts files from the /usr/share/nginx/html/models directory in the image
3. Saves the extracted files to a local directory

It displays progress information during operations and handles potential errors.
"""

import docker
import os
import tarfile
import io
import shutil


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


def extract_models_from_image(image_name, input_dir, output_dir):
    """
    Extract files from the /usr/share/nginx/html/models directory in the Docker image.

    Args:
        image_name (str): The name of the Docker image to extract files from
        input_dir (str): The directory inside the Docker image to extract files from
        output_dir (str): The local directory to save extracted files to

    Returns:
        bool: True if successful, False otherwise
    """
    # Initialize the Docker client
    client = docker.from_env()

    print(f"Extracting model files from {image_name}...")

    try:
        # Create a container (but don't run it)
        container = client.containers.create(image_name)

        # Get the archive of the models directory
        bits, _ = container.get_archive(input_dir)

        # Create a tar stream from the bits
        tar_stream = io.BytesIO()
        for chunk in bits:
            tar_stream.write(chunk)
        tar_stream.seek(0)

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Extract all files from the tar archive
        with tarfile.open(fileobj=tar_stream) as tar:
            # The archive will have a directory structure, so we need to handle that
            # Get all members of the tar archive
            members = tar.getmembers()

            if not members:
                print("No files found in the models directory.")
                container.remove()
                return False

            print(f"Found {len(members)} items in the archive.")

            # Extract all files, preserving directory structure
            for member in members:
                # Get the original path and modify it to remove the base directory
                orig_path = member.name
                # The first part will be 'models', so we remove that
                parts = orig_path.split("/", 1)
                if len(parts) > 1:
                    new_path = parts[1]  # Take everything after the first '/'
                else:
                    new_path = (
                        ""  # This is the base 'models' directory itself
                    )

                # Skip directories - we'll create them as needed for files
                if member.isdir():
                    continue

                # Extract the file
                file_obj = tar.extractfile(member)
                if file_obj is not None:
                    # Create directories if they don't exist
                    full_output_path = os.path.join(output_dir, new_path)
                    os.makedirs(
                        os.path.dirname(full_output_path), exist_ok=True
                    )

                    # Write the file
                    with open(full_output_path, "wb") as f:
                        shutil.copyfileobj(file_obj, f)

                    print(f"Extracted: {new_path}")

        # Remove the temporary container
        container.remove()

        print(
            "\nSuccessfully extracted model files to "
            f"{os.path.abspath(output_dir)}"
        )
        return True

    except docker.errors.APIError as e:
        print(f"Error accessing Docker image: {e}")
        return False
    except docker.errors.NotFound as e:
        print(f"Error: The specified path was not found in the image: {e}")
        return False
    except tarfile.TarError as e:
        print(f"Error extracting tar archive: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False


if __name__ == "__main__":
    # The specific image to pull
    IMAGE_NAME = "ionutms/3d-model-server:latest"

    # Pull the Docker image
    pull_docker_image(IMAGE_NAME)

    # Extract models from the image
    extract_models_from_image(
        IMAGE_NAME,
        "/usr/share/nginx/html/models",
        "./models",
    )
