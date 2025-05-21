"""Docker Image Pull, Extract, and Build Script.

This script:
1. Pulls the ionutms/3d-model-server:latest Docker image
2. Extracts files from the /usr/share/nginx/html/models directory in the image
3. Saves the extracted files to a local directory
4. Moves any files from new_models directory to models directory
5. Rebuilds the Docker image from a provided Dockerfile
6. Pushes the image to the registry
7. Cleans up local model files after successful push

"""

import io
import os
import shutil
import tarfile

import docker


def pull_docker_image(image_name):
    """Pull a Docker image and display progress information.

    Args:
        image_name (str):
            The name of the Docker image to pull (including tag if specified)

    Returns:
        bool: True if successful, False otherwise
    """
    # Initialize the Docker client
    client = docker.from_env()

    print(f"Pulling Docker image: {image_name}")

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
    """Extract files from a Docker image and save them to a local directory.

    Args:
        image_name (str): The name of the Docker image to extract files from
        input_dir (str):
            The directory inside the Docker image to extract files from
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
            members = tar.getmembers()

            if not members:
                print("No files found in the models directory.")
                container.remove()
                return False

            print(f"Found {len(members)} items in the archive.")

            # Extract all files, preserving directory structure
            for member in members:
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


def move_new_models_to_models(new_models_dir, models_dir):
    """Move all files from new_models directory to models directory.

    Keep the new_models directory structure but remove the moved files.

    Args:
        new_models_dir (str): Path to the new_models directory
        models_dir (str):
            Path to the models directory where files will be moved

    Returns:
        bool: True if successful, False otherwise
    """
    print(f"Moving files from {new_models_dir} to {models_dir}...")

    # Check if new_models directory exists
    if not os.path.exists(new_models_dir):
        print(f"Error: Directory {new_models_dir} does not exist.")
        return False

    # Create models directory if it doesn't exist
    os.makedirs(models_dir, exist_ok=True)

    # Keep track of the number of files moved
    files_moved = 0
    files_overwritten = 0

    try:
        # Walk through the new_models directory structure
        for root, _, files in os.walk(new_models_dir):
            # Get the relative path from new_models_dir
            rel_path = os.path.relpath(root, new_models_dir)

            # Create the corresponding directory
            # in models_dir if it doesn't exist
            if rel_path != ".":
                target_dir = os.path.join(models_dir, rel_path)
                os.makedirs(target_dir, exist_ok=True)
            else:
                target_dir = models_dir

            # Copy each file, overwriting if needed, then remove the original
            for file in files:
                source_file = os.path.join(root, file)
                target_file = os.path.join(target_dir, file)

                # Check if the file already exists in the target directory
                if os.path.exists(target_file):
                    files_overwritten += 1

                # Copy file to models directory
                shutil.copy2(source_file, target_file)

                # Remove the original file but keep the directory structure
                os.remove(source_file)
                files_moved += 1

                print(
                    "Copied to models & removed from new_models: "
                    f"{os.path.relpath(source_file, new_models_dir)}"
                )

        # Don't remove empty directories - keep the structure
        print(
            f"\nSuccessfully processed {files_moved} files from "
            f"{new_models_dir} to {models_dir}"
        )
        print(
            f"The {new_models_dir} directory structure has been preserved, "
            "but all files have been removed."
        )
        if files_overwritten > 0:
            print(
                f"Overwritten {files_overwritten} "
                f"existing files in {models_dir}"
            )
        return True

    except PermissionError as e:
        print(f"Permission error: {e}")
        return False
    except OSError as e:
        print(f"OS error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False


def build_docker_image(image_name, dockerfile_path="."):
    """Build a Docker image from a Dockerfile with the --no-cache option.

    Args:
        image_name (str): The name (and optionally tag) for the built image
        dockerfile_path (str):
            The path to the directory containing the Dockerfile
            (defaults to current directory)

    Returns:
        bool: True if successful, False otherwise
    """
    # Initialize the Docker client
    client = docker.from_env()

    print(f"Building Docker image: {image_name}")

    try:
        _, build_logs = client.images.build(
            path=dockerfile_path,
            tag=image_name,
            nocache=True,
            pull=False,
            rm=True,
        )

        # Display build logs
        for log_line in build_logs:
            if "stream" in log_line:
                # Remove trailing newlines for cleaner output
                log_text = log_line["stream"].rstrip()
                if log_text:
                    print(log_text)

        # Verify the image was built successfully
        images = client.images.list()
        image_found = any(
            image_name in img.tags for img in images if img.tags
        )

        if image_found:
            print(f"\nSuccessfully built {image_name}")
            return True
        else:
            print(
                f"\nWarning: Cannot verify if {image_name} "
                "was built successfully."
            )
            return False

    except docker.errors.BuildError as e:
        print(f"Error building Docker image: {e}")
        return False
    except docker.errors.APIError as e:
        print(f"Docker API error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False


def push_docker_image(local_image, remote_image):
    """Push a Docker image to a remote registry.

    Args:
        local_image (str): The name of the local image to push
        remote_image (str): The name of the remote image (including registry)

    Returns:
        bool: True if successful, False otherwise

    """
    client = docker.from_env()

    try:
        print(f"Tagging image {local_image} as {remote_image}...")
        image = client.images.get(local_image)
        image.tag(remote_image)

        print(f"Pushing image {remote_image} to registry...\n")
        push_logs = client.images.push(remote_image, stream=True, decode=True)

        success = True
        for entry in push_logs:
            if "status" in entry and "id" in entry:
                line = f"{entry['id']}: {entry['status']}"
                if "progress" in entry:
                    line += f" {entry['progress']}"
                print(line)
            elif "status" in entry:
                print(entry["status"])
            elif "error" in entry:
                print(f"Error: {entry['error']}")
                success = False
                break

        if success:
            print("\n✅ Image pushed successfully.")
            return True
        else:
            print("\n❌ Failed to push image.")
            return False

    except docker.errors.ImageNotFound:
        print(f"Error: Image '{local_image}' not found.")
        return False
    except docker.errors.APIError as e:
        print(f"Docker API error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False


def cleanup_model_files(models_dir):
    """Remove all files from the models directory after successful image push.

    Args:
        models_dir (str): Path to the models directory to clean up

    Returns:
        bool: True if successful, False otherwise
    """
    print(f"\nCleaning up local model files from {models_dir}...")

    # Check if models directory exists
    if not os.path.exists(models_dir):
        print(f"Error: Directory {models_dir} does not exist.")
        return False

    files_removed = 0
    try:
        # Walk through the models directory structure and remove all files
        for root, _, files in os.walk(models_dir, topdown=False):
            # First remove all files in current directory
            for file in files:
                file_path = os.path.join(root, file)
                os.remove(file_path)
                files_removed += 1
                print(f"Removed: {os.path.relpath(file_path, models_dir)}")

            # Then remove empty directories
            if root != models_dir:
                try:
                    os.rmdir(root)
                    print(
                        "Removed empty directory: "
                        f"{os.path.relpath(root, models_dir)}"
                    )
                except OSError:
                    # Directory not empty, which is fine
                    pass

        print(
            f"\n✅ Successfully removed {files_removed} "
            f"files from {models_dir}"
        )
        print(
            f"The {models_dir} directory has been preserved but is now empty."
        )
        return True

    except PermissionError as e:
        print(f"Permission error during cleanup: {e}")
        return False
    except OSError as e:
        print(f"OS error during cleanup: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error during cleanup: {e}")
        return False


if __name__ == "__main__":
    # The specific image to pull and rebuild
    IMAGE_NAME = "ionutms/3d-model-server:latest"
    MODELS_DIR = "./models"
    NEW_MODELS_DIR = "./new_models"

    # Pull the Docker image
    pull_success = pull_docker_image(IMAGE_NAME)

    # Extract models from the image
    extract_success = False
    if pull_success:
        extract_success = extract_models_from_image(
            IMAGE_NAME, "/usr/share/nginx/html/models", MODELS_DIR
        )

    # Move any files from new_models to models (with overwrite)
    move_success = move_new_models_to_models(NEW_MODELS_DIR, MODELS_DIR)

    # Rebuild the Docker image from the Dockerfile in the current directory
    build_success = build_docker_image(IMAGE_NAME)

    # Push the Docker image to the registry
    push_success = push_docker_image(IMAGE_NAME, IMAGE_NAME)

    # Clean up local model files after successful push
    if push_success:
        cleanup_model_files(MODELS_DIR)
    else:
        print(f"\nSkipping cleanup of {MODELS_DIR} due to failed image push.")
