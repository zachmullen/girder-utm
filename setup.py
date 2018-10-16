from setuptools import setup, find_packages

setup(
    name='girder-utm',
    version='1.0.0',
    description='UTM algorithms in Girder Worker',
    author='Kitware, Inc.',
    url='https://github.com/zachmullen/girder-utm',
    license='Apache 2.0',
    classifiers=[
      'Development Status :: 5 - Production/Stable',
      'Environment :: Web Environment',
      'License :: OSI Approved :: Apache Software License'
    ],
    include_package_data=True,
    packages=find_packages(exclude=['plugin_tests']),
    zip_safe=False,
    install_requires=[
        'girder>=3.0.0a1',
        'girder-jobs>=3.0.0a1',
        'girder-worker',
        'girder-worker-utils>=0.7.2'
    ],
    entry_points={
        'girder.plugin': ['utm = girder_utm:UtmPlugin']
    }
)
