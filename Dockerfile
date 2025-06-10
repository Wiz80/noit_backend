FROM --platform=$TARGETPLATFORM python:3.12-slim
WORKDIR /app

# Set build arguments for architecture-specific optimization
ARG TARGETPLATFORM
ARG BUILDPLATFORM
RUN echo "Building on $BUILDPLATFORM for $TARGETPLATFORM"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    cmake \
    python3-dev \
    libffi-dev \
    libblas-dev \
    liblapack-dev \
    gfortran \
    git \
    curl \
    wget \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry

# Copy pyproject.toml and poetry.lock (if it exists)
COPY pyproject.toml ./
COPY poetry.lock* ./

# Configure poetry to not use virtualenvs inside Docker
RUN poetry config virtualenvs.create false

# Install dependencies with architecture-specific optimizations
RUN poetry install --without dev --no-interaction --no-ansi --no-root

# Install Playwright browsers
RUN playwright install --with-deps chromium

# Install Spanish model
RUN python -m spacy download es_core_news_sm
# Install English model
RUN python -m spacy download en_core_web_sm

# Copy application code
COPY . .

# Expose the port the app runs on
EXPOSE 8000 