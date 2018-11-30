from girder.api import access
from girder.api.describe import Description, autoDescribeRoute
from girder.api.rest import Resource, filtermodel
from girder.constants import AccessType, TokenScope, SortDir
from girder.models.file import File
from girder.models.folder import Folder
from girder.models.item import Item
from girder.models.user import User
from girder.plugin import getPlugin, GirderPlugin
from girder_jobs.models.job import Job
from girder_worker.docker.tasks import docker_run
from girder_worker.docker.transforms import VolumePath
from girder_worker.docker.transforms.girder import (
    GirderFolderIdToVolume, GirderUploadVolumePathToFolder, GirderFileIdToVolume)


class UTM(Resource):

    def __init__(self):
        super(UTM, self).__init__()
        self.resourceName = 'utm'

        self.route('GET', ('demo',), self.getDemoData)
        self.route('PUT', ('demo',), self.setDemoData)
        self.route('GET', ('example',), self.listExamples)
        self.route('PUT', (':id', 'examples_folder'), self.setExamplesFolder)
        self.route('POST', ('validate',), self.validate)
        self.route('GET', ('job',), self.listJobs)
        self.route('POST', (), self.run)

    @access.admin
    @autoDescribeRoute(
        Description('Set the folder containing example screenshots.')
        .modelParam('id', 'The ID of the folder containing the examples as items.',
                    model=Folder, level=AccessType.ADMIN)
        .param('enabled', 'Whether this is the example folder.', dataType='boolean',
                default=True, required=False))
    def setExamplesFolder(self, folder, enabled):
        op = '$set' if enabled else '$unset'
        Folder().update({'_id': folder['_id']}, {op: {
            'utmExampleFolder': True
        }}, multi=False)
        return enabled


    @access.public
    @filtermodel(Item)
    @autoDescribeRoute(
        Description('List example utm screenshot images as items.'))
    def listExamples(self):
        folder = Folder().findOne({'utmExampleFolder': True})
        if folder is None:
            return []
        return list(Folder().childItems(folder))


    @access.admin
    @autoDescribeRoute(
        Description('Set the folder containing input demo data.')
        .modelParam('folderId', 'The ID of the folder containing the examples as items.',
                    model=Folder, level=AccessType.ADMIN, destName='folder', paramType='formData')
        .modelParam('paramsId', 'The file representing the input params (CSV format).', model=File,
                    level=AccessType.ADMIN, destName='paramsFile', paramType='formData')
        .param('enabled', 'Whether these are the active demo items.', dataType='boolean',
                default=True, required=False))
    def setDemoData(self, folder, paramsFile, enabled):
        op = '$set' if enabled else '$unset'
        Folder().update({'_id': folder['_id']}, {op: {
            'utmDemoData': True
        }}, multi=False)
        File().update({'_id': paramsFile['_id']}, {op: {
            'utmDemoData': True
        }}, multi=False)
        return enabled


    @access.public
    @autoDescribeRoute(
        Description('Get the current demo data directory and variable file'))
    def getDemoData(self):
        folder = Folder().findOne({'utmDemoData': True})
        paramsFile = File().findOne({'utmDemoData': True})
        return {
            'folder': folder,
            'paramsFile': paramsFile,
        }


    @access.user(scope=TokenScope.DATA_READ)
    @autoDescribeRoute(
        Description('Validate that UTM can be run on a given folder.')
        .modelParam('folderId', 'The input folder ID.', model=Folder, level=AccessType.READ,
                    destName='folder', paramType='formData')
        .modelParam('paramsId', 'The file representing the input params (CSV format).', model=File,
                    level=AccessType.READ, destName='paramsFile', paramType='formData')
        .modelParam('outputFolderId', 'The output folder ID.', model=Folder, level=AccessType.READ,
                    destName='outputFolder', paramType='formData'))
    def validate(self, folder, paramsFile, outputFolder):
        """
        Check a folder for the necessary files and corresponding CSV variables.
        """
        pass


    @access.user
    @filtermodel(Job)
    @autoDescribeRoute(
        Description('List utm jobs for a user.')
        .modelParam('userId', 'The user ID.', model=User, paramType='formData',
                    level=AccessType.READ, required=False)
        .pagingParams(defaultSort='created', defaultSortDir=SortDir.DESCENDING, defaultLimit=10)
    )
    def listJobs(self, user, limit, offset, sort):
        user = user or self.getCurrentUser()
        cursor = Job().find({
            'userId': user['_id'],
            'utmFolderId': {'$exists': True},
        }, sort=sort)
        return list(Job().filterResultsByPermission(
            cursor=cursor, user=self.getCurrentUser(), level=AccessType.READ, limit=limit,
            offset=offset))


    @access.user(scope=TokenScope.DATA_WRITE)
    @autoDescribeRoute(
        Description('Run UTM algorithm on a folder.')
        .modelParam('folderId', 'The input folder ID.', model=Folder, level=AccessType.READ,
                    destName='folder', paramType='formData')
        .modelParam('paramsId', 'The file representing the input params (CSV format).', model=File,
                    level=AccessType.READ, destName='paramsFile', paramType='formData')
        .modelParam('outputFolderId', 'The output folder ID.', model=Folder, level=AccessType.WRITE,
                    destName='outputFolder', paramType='formData'))
    def run(self, folder, paramsFile, outputFolder):
        outpath = VolumePath('__results__')
        # self.validate(folder)
        job = docker_run.delay('samuelgerber/utm', container_args=[
            GirderFolderIdToVolume(folder['_id']),
            GirderFileIdToVolume(paramsFile['_id']),
            '--workingfolder', outpath
        ], girder_job_title='UTM: ' + folder['name'], girder_result_hooks=[
            GirderUploadVolumePathToFolder(outpath, outputFolder['_id'])
        ]).job
        job['utmFolderId'] = folder['_id']
        job['utmOutputFolderId'] = outputFolder['_id']
        return Job().save(job)


class UtmPlugin(GirderPlugin):
    DISPLAY_NAME = 'UTM algorithm'

    def load(self, info):
        getPlugin('worker').load(info)
        info['apiRoot'].utm = UTM()

        Job().exposeFields(level=AccessType.READ, fields={'utmFolderId', 'utmOutputFolderId'})
