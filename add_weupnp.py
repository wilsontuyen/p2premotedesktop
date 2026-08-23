import re

build_file = r'D:\SOFT\Coder\Android\app\build.gradle.kts'
with open(build_file, 'r', encoding='utf-8') as f:
    build_content = f.read()

# Add org.bitlet:weupnp:0.1.4 to dependencies
if 'org.bitlet:weupnp' not in build_content:
    # Find dependencies { block
    dep_pattern = re.compile(r'(dependencies \{)')
    build_content = dep_pattern.sub(r'\1\n    implementation("org.bitlet:weupnp:0.1.4")', build_content)
    with open(build_file, 'w', encoding='utf-8') as f:
        f.write(build_content)
