"""
Strips unused AWS service clients out of the AWS SDK v2 "bundle" jar that
Hadoop's S3A support depends on (software.amazon.awssdk:bundle, pulled in by
the -Phadoop-cloud profile). That jar ships every AWS service (400+, ~640MB),
the vast majority unused here - S3A only ever touches S3 itself plus a
handful of services used by its credential provider chain. Iceberg's
GlueCatalog is unaffected: iceberg-aws-bundle ships its own separately
shaded copy of the AWS SDK under org.apache.iceberg.shaded.software.amazon.
awssdk, so it never touches this jar.

Usage:
  python strip-aws-sdk-bundle.py <path-to-assembly-jars-dir>
"""

import sys
import zipfile
from pathlib import Path

# s3: the filesystem itself.
# sts: assume-role based credential providers.
# kms: SSE-KMS encrypted buckets.
# sso/ssooidc: AWS SDK's default credential chain includes SSO profile
# resolution.
KEEP_SERVICES = {"s3", "sts", "kms", "sso", "ssooidc"}


def should_keep(name: str) -> bool:
    parts = name.split("/")
    if len(parts) >= 5 and parts[:4] == ["software", "amazon", "awssdk", "services"]:
        return parts[4] in KEEP_SERVICES
    return True


def strip(jar_path: Path) -> None:
    tmp_path = jar_path.with_suffix(jar_path.suffix + ".tmp")
    kept = 0
    removed = 0
    with zipfile.ZipFile(jar_path, "r") as src, zipfile.ZipFile(
        tmp_path, "w", zipfile.ZIP_DEFLATED
    ) as dst:
        for item in src.infolist():
            if should_keep(item.filename):
                dst.writestr(item, src.read(item.filename))
                kept += 1
            else:
                removed += 1

    before = jar_path.stat().st_size
    tmp_path.replace(jar_path)
    after = jar_path.stat().st_size
    print(
        f"{jar_path.name}: kept {kept} entries, removed {removed} entries, "
        f"{before / 1024 / 1024:.1f} MB -> {after / 1024 / 1024:.1f} MB"
    )


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: strip-aws-sdk-bundle.py <jars-dir>", file=sys.stderr)
        sys.exit(1)

    jars_dir = Path(sys.argv[1])
    matches = sorted(jars_dir.glob("bundle-*.jar"))
    if not matches:
        print(f"no bundle-*.jar found in {jars_dir}", file=sys.stderr)
        sys.exit(1)

    for jar_path in matches:
        strip(jar_path)


if __name__ == "__main__":
    main()
