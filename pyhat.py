# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Pyhat
                                 A QGIS plugin
 Uses PyHAT algorithms to allow application of these algorithms through QGIS
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2018-07-11
        git sha              : $Format:%H$
        copyright            : (C) 2018 by USGS Astrogeology
        email                : tthatcher@usgs.gov
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from PyQt5.QtCore import QSettings, QTranslator, qVersion, QCoreApplication
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QMenu
from qgis.core import *

import sys
import qgis.utils
import gdal
import numpy as np

from functools import partial
from plio.io.io_gdal import array_to_raster
from libpyhat.io.io_crism import open as crism_open
from libpyhat.io.io_moon_mineralogy_mapper import open as m3_open
from libpyhat.derived.m3 import pipe, supplemental, ip, new
from libpyhat.derived.crism import crism_algs
from unittest import mock
import inspect
import os




# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .pyhat_dialog import PyhatDialog
from pathlib import Path

# Grabs the home directory by default
home = str(Path.home())

# Allows user to set outpath
PyhatDialog.M3_outpath = sys.modules[__name__]
PyhatDialog.img_outpath = home

class Pyhat:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'Pyhat_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Create the dialog (after translation) and keep reference
        self.dlg = PyhatDialog()

        # Declare instance attributes
        self.actions = []
        self.m3 = self.tr(u'&M3')
        self.crism = self.tr(u'&Crism')

        # TODO: We are going to let the user set this up in a future iteration
        # self.toolbar = self.iface.addToolBar(u'Pyhat')
        # self.toolbar.setObjectName(u'Pyhat')

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('Pyhat', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        m3 = False,
        crism = False,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=False,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if m3:
            self.iface.addPluginToMenu(
                self.m3,
                action)
        if crism:
            self.iface.addPluginToMenu(
                self.crism,
                action)


        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        self.icon_path = ':/plugins/pyhat/icon.png'

        self.menu = QMenu( "&PyHAT", self.iface.mainWindow().menuBar() )
        actions = self.iface.mainWindow().menuBar().actions()
        lastAction = actions[-1]
        self.iface.mainWindow().menuBar().insertMenu( lastAction, self.menu )

        self.m3_menu = QMenu( "&M3", self.menu )
        self.menu.insertMenu( lastAction, self.m3_menu )

        self.crism_menu = QMenu( "&CRISM", self.menu )
        self.menu.insertMenu( lastAction, self.crism_menu )

        self.action = QAction(QIcon(self.icon_path),"Setup Outpath", self.iface.mainWindow())
        self.action.triggered.connect(self.setup_outpath)
        self.menu.addAction( self.action )

        # Menus for M3 menu
        self.m3_pipe_functions = QMenu( "&Pipe", self.m3_menu )
        self.m3_menu.insertMenu( lastAction, self.m3_pipe_functions )

        self.m3_ip_functions = QMenu( "&IP", self.m3_menu )
        self.m3_menu.insertMenu( lastAction, self.m3_ip_functions )

        self.m3_supplmental_functions = QMenu( "&Supplemental", self.m3_menu )
        self.m3_menu.insertMenu( lastAction, self.m3_supplmental_functions )

        # Adds actions to pipe menu
        self.build_menus(pipe, self.m3_pipe_functions)
        self.build_menus(supplemental, self.m3_supplmental_functions)
        self.build_menus(ip, self.m3_ip_functions)

        # Adds actions to crism
        # TODO: Build Menus for CRISM algorithms
        self.build_menus(crism_algs, self.crism_menu)

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&PyHat'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        # del self.toolbar

    def build_menus(self, module, menu_name, package=None):
        """
        Parameters
        ----------
        module : Name of python module you want to run functions out of

        img : Full path to M3 image img_tiff

        filepath: Path to where you want the new tiffs to be generated

        Returns
        -------
         : tiff image
        """
        # Grabs all functions in a module
        package_funcs = inspect.getmembers(module, inspect.isfunction)

        not_called = []
        for function in package_funcs:
            self.action = QAction(QIcon(self.icon_path), str(function[0]), menu_name)
            self.action.triggered.connect(partial(self.run_algorithm, module, str(function[0])))
            menu_name.addAction( self.action )

    def run_algorithm(self, module, func=None):
        """Run method that performs all the real work"""

        # Gets the current layer
        layer = self.iface.activeLayer()
        layer_path = layer.dataProvider().dataSourceUri()

        if module == crism_algs:
            img = crism_open(layer_path)

        else:
            # Opens the image using plio for reading
            img = m3_open(layer_path)

        # Applies the algorithm specified
        modified_img = getattr(module, str(func))(img)

        # Stores the name of the image file

        base = os.path.basename(layer_path)
        new_filename = (str(func) + '_' + base + '.tif')
        
        # Creates the new filepath for the image
        new_filepath = os.path.join(str(PyhatDialog.img_outpath), new_filename)

        try:
            img.spatial_reference
            array_to_raster(modified_img, new_filepath, bittype='GDT_Float32',
                                       projection=img.spatial_reference)
        except:
            # Writes the tiff to the user specified location
            array_to_raster(modified_img, new_filepath, bittype='GDT_Float32')

        # Grabs the new tiff and adds it into QGIS
        self.iface.addRasterLayer(new_filepath, new_filename)

        return 0

    def setup_outpath(self):
        """Run method that performs all the real work"""
        # show the dialog
        layers = [layer for layer in QgsProject.instance().mapLayers().values()]
        layer_list = []

        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            outpath = self.dlg.lineEdit.text()
            PyhatDialog.img_outpath = outpath

        return None
