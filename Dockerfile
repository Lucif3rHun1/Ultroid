# Ultroid - UserBot
# Copyright (C) 2021-2026 TeamUltroid
# This file is a part of < https://github.com/TeamUltroid/Ultroid/ >
# PLease read the GNU Affero General Public License in <https://www.github.com/TeamUltroid/Ultroid/blob/main/LICENSE/>.

FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ffmpeg \
       mediainfo \
       git \
    && rm -rf /var/lib/apt/lists/*

# set timezone
ENV TZ=Asia/Kolkata
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

COPY installer.sh .

RUN bash installer.sh

# changing workdir
WORKDIR "/root/TeamUltroid"

# start the bot.
CMD ["bash", "startup"]
