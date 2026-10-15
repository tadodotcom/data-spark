#!/usr/bin/env python3
"""Replace jars in deps/jars/ of an existing pyspark sdist.

Only tado-custom-spark-iceberg.jar depends on the Iceberg version; the rest of
the distribution (Spark itself, the patched Hive, the stripped AWS SDK bundle,
tado-custom-spark-glue.jar) does not. Bumping Iceberg therefore never needs a
full Spark rebuild: take the sdist from any previous release with the same
Spark version and swap just that one jar:

    replace-jars.py BASE_SDIST OUTPUT_SDIST \\
        --remove 'tado-custom-spark-iceberg*.jar' \\
        iceberg/target/tado-custom-spark-iceberg.jar

Every --remove pattern must match at least one jar. Added jars keep their file
name, and pyspark.egg-info/SOURCES.txt is updated to match.
"""

import argparse
import fnmatch
import gzip
import io
import sys
import tarfile
from pathlib import Path, PurePosixPath


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("base_sdist", type=Path)
    parser.add_argument("output_sdist", type=Path)
    parser.add_argument(
        "--remove",
        action="append",
        default=[],
        metavar="GLOB",
        help="Jar file name pattern to remove from deps/jars/",
    )
    parser.add_argument("jars", nargs="+", type=Path, help="Jars to add")
    args = parser.parse_args()

    removed: dict[str, list[str]] = {pattern: [] for pattern in args.remove}
    added = [jar.name for jar in args.jars]

    def matching_pattern(name: str) -> str | None:
        path = PurePosixPath(name)
        if path.parent.name != "jars" or path.parent.parent.name != "deps":
            return None
        names_to_replace = [*args.remove, *added]
        return next(
            (p for p in names_to_replace if fnmatch.fnmatch(path.name, p)),
            None,
        )

    # mtime=0 in the gzip header so identical inputs give an identical output.
    with (
        tarfile.open(args.base_sdist, "r:gz") as src,
        gzip.GzipFile(args.output_sdist, "wb", mtime=0) as gz,
        tarfile.open(fileobj=gz, mode="w", format=src.format) as dst,
    ):
        template: tarfile.TarInfo | None = None
        for member in src:
            pattern = matching_pattern(member.name) if member.isfile() else None
            if pattern is not None:
                # Ownership/mode/mtime for the added jars.
                template = member
                if pattern in removed:
                    removed[pattern].append(member.name)
                continue
            if member.isfile() and member.name.endswith(
                "pyspark.egg-info/SOURCES.txt"
            ):
                sources = src.extractfile(member).read().decode().splitlines()
                sources = [s for s in sources if not matching_pattern(s)]
                sources = sorted(sources + [f"deps/jars/{a}" for a in added])
                data = ("\n".join(sources) + "\n").encode()
                member.size = len(data)
                dst.addfile(member, io.BytesIO(data))
            elif member.isfile():
                dst.addfile(member, src.extractfile(member))
            else:
                dst.addfile(member)

        unmatched = [pattern for pattern, names in removed.items() if not names]
        if template is None or unmatched:
            dst.close()
            args.output_sdist.unlink()
            print(
                f"No jar in {args.base_sdist} matches {unmatched or args.remove}",
                file=sys.stderr,
            )
            return 1

        root = PurePosixPath(template.name).parent
        for jar in args.jars:
            info = tarfile.TarInfo(str(root / jar.name))
            info.mode, info.mtime = template.mode, template.mtime
            info.uid, info.gid = template.uid, template.gid
            info.uname, info.gname = template.uname, template.gname
            info.size = jar.stat().st_size
            with jar.open("rb") as f:
                dst.addfile(info, f)

    for pattern, names in removed.items():
        print(f"Removed {', '.join(names)} (--remove {pattern})")
    print(f"Added {', '.join(added)} to {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
