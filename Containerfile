# Use Red Hat Universal Base Image (UBI) 9 Minimal
FROM registry.access.redhat.com/ubi9/ubi-minimal:latest

# Install Python 3.11, build tools, network tools, and shadow-utils (for user management)
RUN microdnf update -y && microdnf install -y \
    python3.11 \
    python3.11-pip \
    python3.11-devel \
    gcc \
    gcc-c++ \
    make \
    iputils \
    shadow-utils \
    && microdnf clean all \
    && alternatives --install /usr/bin/python python /usr/bin/python3.11 1 \
    && alternatives --install /usr/bin/pip pip /usr/bin/pip3.11 1

# ENTERPRISE FIX 1: Create a dedicated, non-root user
RUN useradd -m -s /bin/bash netopsuser

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .

# ENTERPRISE FIX 3 (Prep): Upgrade pip and install pysqlite3-binary to bypass the UBI sqlite issue
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir pysqlite3-binary && \
    pip install --no-cache-dir -r requirements.txt

RUN python -m spacy download en_core_web_sm

# Copy the rest of the code and assign ownership to the non-root user
COPY --chown=netopsuser:netopsuser . .

# Give the runtime user a stable writable location for Streamlit history/state.
ENV NETOPS_DATA_DIR=/home/netopsuser/.netops
RUN mkdir -p /home/netopsuser/.netops /app/vector_db && \
    chown -R netopsuser:netopsuser /app /home/netopsuser

# Switch away from the root user
USER netopsuser

# ENTERPRISE FIX 2: Explicitly declare the vector database directory as a volume
VOLUME ["/app/vector_db"]

# Run the ingestion pipeline (or app.py when you build the API)
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.fileWatcherType=none"]
