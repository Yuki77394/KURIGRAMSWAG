#
# Copyright (C) 2021-2022 by SWAGGYMUSIC@Github, < https://github.com/Yuki77394/NEWSRMUSIC >.
# This file is part of < https://github.com/Yuki77394/NEWSRMUSIC > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Yuki77394/NEWSRMUSIC/blob/master/LICENSE >
#
# All rights reserved.

import sys

print("🚀 Starting SWAGGYMUSIC Bot...")

try:
    # Run the package as module
    import runpy

    runpy.run_module("SWAGGYMUSIC", run_name="__main__")
except Exception as e:
    print("❌ Bot crashed with error:", e)
    sys.exit(1)
