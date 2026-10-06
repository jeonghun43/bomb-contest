# toolchain/Dockerfile - the compiler the original CMU bomb was built with.
#
# The CS:APP 3e self-study bomb reports, in .comment and DW_AT_producer:
#     GCC: (Ubuntu 4.8.1-2ubuntu1~12.04) 4.8.1      <- compiler
#     GCC: (Ubuntu/Linaro 4.6.3-1ubuntu5) 4.6.3     <- crt objects from libc6-dev
#     -O1 -fstack-protector (-ggdb on bomb.c only)
# Building on Ubuntu 12.04 with that exact gcc-4.8 package from the
# ubuntu-toolchain-r PPA reproduces both lines. See
# specs/003-practice-bank/research.md.
#
#   docker build -t bomblab-gcc48 toolchain/
#
# Ubuntu 12.04 is end of life, so apt goes to old-releases, and the PPA index
# only lists a later 4.8.4, so the 4.8.1 packages are fetched by file name.

FROM ubuntu:12.04

RUN printf '%s\n' \
        'deb http://old-releases.ubuntu.com/ubuntu precise main universe' \
        'deb http://old-releases.ubuntu.com/ubuntu precise-updates main universe' \
        'deb http://old-releases.ubuntu.com/ubuntu precise-security main universe' \
        'deb http://ppa.launchpad.net/ubuntu-toolchain-r/test/ubuntu precise main' \
        > /etc/apt/sources.list \
 && apt-get update -qq || true

# Build dependencies of gcc-4.8 (libisl10 / libcloog-isl4 come from the PPA).
RUN apt-get install -y -qq --force-yes \
        wget binutils make libc6-dev \
        libgmp10 libmpfr4 libmpc2 libisl10 libcloog-isl4 zlib1g \
 && rm -rf /var/lib/apt/lists/*

ARG GCC_VER=4.8.1-2ubuntu1~12.04
ARG PPA=https://launchpad.net/~ubuntu-toolchain-r/+archive/ubuntu/test/+files

RUN mkdir /debs && cd /debs \
 && for p in gcc-4.8-base libgcc1 libgomp1 libitm1 libatomic1 libasan0 \
             libtsan0 libquadmath0 libgcc-4.8-dev cpp-4.8 gcc-4.8; do \
        wget -q --no-check-certificate "$PPA/${p}_${GCC_VER}_amd64.deb" \
        || { echo "missing $p"; exit 1; }; \
    done \
 && dpkg -i gcc-4.8-base_*.deb libgcc1_*.deb \
 && dpkg -i libgomp1_*.deb libitm1_*.deb libatomic1_*.deb libasan0_*.deb \
            libtsan0_*.deb libquadmath0_*.deb \
 && dpkg -i libgcc-4.8-dev_*.deb cpp-4.8_*.deb gcc-4.8_*.deb \
 && ln -sf /usr/bin/gcc-4.8 /usr/local/bin/gcc \
 && ln -sf /usr/bin/gcc-4.8 /usr/local/bin/cc \
 && rm -rf /debs

RUN gcc --version | head -1 | grep -q '4.8.1-2ubuntu1~12.04'

WORKDIR /src
