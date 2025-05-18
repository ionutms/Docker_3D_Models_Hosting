FROM nginx:alpine

# Create directory for 3D models
RUN mkdir -p /usr/share/nginx/html/models

# Copy all local 3D models into the image
COPY ./models/ /usr/share/nginx/html/models/

# Copy the NGINX configuration file
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy an index page for browsing models
COPY index.html /usr/share/nginx/html/

# Add a placeholder to verify it's working
RUN echo "3D Model Server is running!" > /usr/share/nginx/html/status.txt

# Expose port 80 for web traffic
EXPOSE 80

# Command to run when container starts
CMD ["nginx", "-g", "daemon off;"]