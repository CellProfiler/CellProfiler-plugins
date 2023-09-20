# OMERO Plugins

[OMERO](https://www.openmicroscopy.org/omero/) is an image data management server developed by the Open Microscopy Environment. 
It allows for the storage and retrieval of image datasets and associated metadata.


## Using OMERO with CellProfiler

The OMERO plugins can be used to connect to an OMERO server and exchange data with CellProfiler. You'll need to supply the server address and login credentials to establish a connection.

The current iteration of the plugins supports a single active connection at any given time. This means that pipelines should only be requesting data from a single OMERO server.

Supplying credentials every run can be repetitive, so the plugins will also detect and make use of tokens set by the [omero-user-token](https://github.com/glencoesoftware/omero-user-token) package. This provides a long-lasting mechanism for 
reconnecting to a previously established OMERO session. N.b. tokens which are set to never expire will only be valid until the OMERO server restarts.

## The connection interface

When installed correctly, OMERO-related entries will be available in the CellProfiler '**Plugins**' menu (this menu only appears when an installed plugin uses it). You'll find _Connect to OMERO_ menu entries allowing you 
to connect to an OMERO server. If a user token already exists this will be used to establish a connection, otherwise you'll see a dialog where credentials can be supplied. You can also use the 
_Connect to OMERO (no token)_ option to skip checking for a login token, this is mostly useful if you need to switch server.

After entering credentials and establishing a connection, a _Set Token_ button is available to create an omero-user-token on your system. This will allow 
you to reconnect to the same server automatically without entering credentials. Tokens are set per-user, and only a single token can be stored at a time. This means that you 
**should not** set tokens if using a shared user account.

An active OMERO connection is required for most functionality in these plugins. A single connection can be made at a time, and the 
plugin will automatically sustain, manage and safely shut down this connection as needed. The OMERO plugin will disconnect automatically when 
quitting CellProfiler. The connection dialog should automatically display if you try to run the plugin without a connection.

When reconnecting via a token, the plugin will display a message clarifying which server was connected to. This message can be disabled by ticking the _do not show again_ box. This 
can be re-enabled using the reader configuration interface in the _File->Configure Readers_ menu. Under the OMEROReader reader config 
you'll also find an option to entirely disable token usage, in case you need to use different credentials elsewhere on your machine.

## Loading image data

The plugin suite includes the OMEROReader image reader, which can be used by both NamesAndTypes and LoadData.

To load images with the OMERO plugin we need to supply an image's unique OMERO ID. In OMERO.web, this is visible in the right pane with an image selected. We can supply image IDs to the file list in two forms:

- As a URL in the format `https://my.omero.server/webclient/?show=image-3654`
- Using the (legacy) format `omero:iid=3654`

Supplying the full URL is recommended, since this provides CellProfiler with the actual server address too.

In previous versions of the integration, you needed to create a text file with one image per line and then use _File->Import->File List_ to load them
into CellProfiler. As of CellProfiler 5 you should be able to simply copy/paste these image links into the file list in the Images module.

There is also a _Browse OMERO for Images_ option in the Plugins menu. This provides a fully featured interface for browsing an OMERO server and adding images to your pipeline.
Images can be added by selecting them and using the _Add to file list_ button, or by dragging from the tree pane onto the main file list.

As for CellProfiler 5, these plugins also now interpret image channels correctly. If the image on OMERO contains multiple channels, you should either set the 
image types in NamesAndTypes to _Color_ mode instead of _Greyscale_. Alternatively you can use the _Extract image planes_ option in the Images module and enable 
splitting by channel to generate a single greyscale entry for each channel in the image.

It should go without saying that the OMERO account you login to the server with needs to have permissions to view/read the image.

It may be advisable to use an [OMERO.script](https://omero.readthedocs.io/en/stable/developers/scripts/index.html) to generate any large file lists that 
you want to load from OMERO.

Some OMERO servers may have the [omero-ms-pixel-buffer](https://github.com/glencoesoftware/omero-ms-pixel-buffer) microservice installed. This provides a conventional 
HTTP API for fetching image data using a specially formatted URL. Since these are seen as standard file downloads the OMERO plugin is not needed to load data from this microservice into CellProfiler.

## Saving data to OMERO

The OMERO integration includes two module plugins for sending data back to OMERO: SaveImagesToOMERO and ExportToOMEROTable.

### SaveImagesToOMERO

The SaveImagesToOMERO plugin functions similarly to SaveImages, but the exported image is instead uploaded to the OMERO server.

Images on OMERO are generally contained within Datasets. Datasets also have a unique ID visible within the right panel of OMERO.web. 
To use the module you'll need to supply the target dataset's ID (or other parent object type), and resulting images will be uploaded to that dataset.

On OMERO image names do not need to be unique (only image IDs). You may want to use metadata fields to construct a distinguishable name for each uploaded image.

At present uploaded images are not linked to any data previously read from OMERO, so make sure you have a means of identifying the image from it's name.

### ExportToOMEROTable

[OMERO tables](https://omero.readthedocs.io/en/stable/developers/Tables.html) are tabular data stores which can be viewed in OMERO.web. Like all OMERO objects, tables are 
associated with a parent object (typically an image or dataset). You'll need to provide an ID for the parent object.

The module functions similarly to ExportToDatabase, in that measurements are uploaded after each image set completes. One caveat is that 
it is not possible to add columns to an OMERO.table after it's initial creation, therefore certain meta-measurements are not available in this module.

To retrieve and analyse data from OMERO.tables in other software, you should be able to use the [omero2pandas](https://github.com/glencoesoftware/omero2pandas) package. This will retrieve 
table data as Pandas dataframes, allowing for their use with the wider Python scientific stack.

## Troubleshooting

- OMERO's Python API currently depends on a very specific version of the `zeroc-ice` package, which can be difficult to build and install. 
The setup.py dependency manager has been supplied with several prebuilt wheels which should cater to most systems. Please raise an issue if you encounter problems.

- When a server connection is established, CellProfiler will ping the server periodically to keep the session going. 
The server connections may time out if your machine enters sleep mode for a prolonged period. If you see errors after waking from sleep, try re-running the _Connect to OMERO_ dialog.

- To upload data you'll need relevant permissions both for the OMERO group and for whichever object you're attaching data to. The plugin's test button will
verify that the object exists, but not that you have write permissions.

- Uploaded images from SaveImagesToOMERO are treated as fresh data by OMERO. Any channel settings and other metadata will not be copied over from loaded image.
