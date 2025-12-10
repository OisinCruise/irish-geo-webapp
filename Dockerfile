# Dockerfile for the Django app
# Using multi-stage build to keep the final image small
# This is what Render uses to build and run the app

# First stage - build Python packages
FROM python:3.11-slim-bookworm AS builder

# These environment variables help with Python performance
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install packages needed to build Python libraries
# GeoDjango needs GDAL, GEOS, and PROJ for spatial operations
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    && rm -rf /var/lib/apt/lists/*

# Create a virtual environment to keep packages isolated
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install all Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# Second stage - production image (much smaller)
FROM python:3.11-slim-bookworm AS production

# Same environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"
ENV DJANGO_SETTINGS_MODULE=config.settings.production

# Install only runtime libraries (not build tools)
# These are the Debian package names for the spatial libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    gdal-bin \
    libgeos-c1v5 \
    libproj25 \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security
# Running as root in containers is a bad idea
RUN groupadd -r django && useradd -r -g django django

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Set working directory
WORKDIR /app

# Copy all the project files
COPY --chown=django:django . .

# Create directories for static files, media, and logs
RUN mkdir -p /app/staticfiles /app/media /app/logs && \
    chown -R django:django /app

# Collect static files during build
# Using a dummy secret key since we don't have the real one at build time
# This is fine - collectstatic doesn't need the real key
RUN DJANGO_SECRET_KEY=build-time-secret python manage.py collectstatic --noinput

# Switch to the non-root user
USER django

# Expose port 8000 (what Gunicorn listens on)
EXPOSE 8000

# Health check - Render uses this to see if the app is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health/')" || exit 1

# Start Gunicorn with settings optimized for Render's free tier
# I had to tune these a lot because the app kept running out of memory
# 1 worker with 2 threads works better than multiple workers on limited RAM
# max-requests restarts workers periodically to prevent memory leaks
# preload loads the app once and shares it between threads (saves memory)
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "2", "--timeout", "120", "--graceful-timeout", "30", "--max-requests", "250", "--max-requests-jitter", "25", "--worker-class", "gthread", "--preload"]