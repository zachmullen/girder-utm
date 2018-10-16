from girder.api import access
from girder.api.describe import Description, autoDescribeRoute
from girder.api.rest import filtermodel
from girder.constants import AccessType, TokenScope
from girder.models.file import File
from girder.models.folder import Folder
from girder.plugin import getPlugin, GirderPlugin
from girder_jobs.models.job import Job
from girder_worker.docker.tasks import docker_run
from girder_worker.docker.transforms import VolumePath
from girder_worker.docker.transforms.girder import (
    GirderFolderIdToVolume, GirderUploadVolumePathToFolder, GirderFileIdToVolume)


@access.user(scope=TokenScope.DATA_WRITE)
@filtermodel(Job)
@autoDescribeRoute(
    Description('Run UTM algorithm on a folder.')
    .modelParam('id', 'The input folder ID.', model=Folder, level=AccessType.READ)
    .modelParam('paramsId', 'The file representing the input params (CSV format).', model=File,
                level=AccessType.READ, destName='paramsFile', paramType='formData')
    .modelParam('outputFolderId', 'The output folder ID.', model=Folder, level=AccessType.WRITE,
                destName='outputFolder', paramType='formData'))
def _runUtm(folder, paramsFile, outputFolder):
    outpath = VolumePath('__results__')
    return docker_run.delay('samuelgerber/utm', container_args=[
        GirderFolderIdToVolume(folder['_id']),
        GirderFileIdToVolume(paramsFile['_id']),
        '--workingfolder', outpath
    ], girder_job_title='UTM: ' + folder['name'], girder_result_hooks=[
        GirderUploadVolumePathToFolder(outpath, outputFolder['_id'])
    ]).job


class UtmPlugin(GirderPlugin):
    DISPLAY_NAME = 'UTM algorithm'

    def load(self, info):
        getPlugin('worker').load(info)

        info['apiRoot'].folder.route('POST', (':id', 'utm'), _runUtm)
