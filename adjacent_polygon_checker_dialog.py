# -*- coding: utf-8 -*-
import os, re, traceback
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QRadioButton, QComboBox, QPushButton, QLineEdit, QFileDialog, QListWidget,
    QListWidgetItem, QCheckBox, QDoubleSpinBox, QProgressBar, QPlainTextEdit,
    QMessageBox, QAbstractItemView, QFormLayout, QSizePolicy, QDialogButtonBox)
from qgis.core import (QgsProject, QgsVectorLayer, QgsWkbTypes, QgsFeature,
    QgsGeometry, QgsField, QgsVectorFileWriter, QgsFeatureRequest, QgsProviderRegistry)
from qgis.PyQt.QtCore import QVariant
from .adjacency_engine import AdjacencyOptions, detect_adjacent_groups
from .attribute_comparator import normalize_value

class AdjacentPolygonCheckerDialog(QDialog):
    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface, self.external_layer = iface, None
        self.value_filters = {}
        self.setWindowTitle("Adjacent Polygon Attribute Checker")
        self.resize(610, 610)
        self.setMinimumSize(560, 520)
        self._build_ui()
        self.refresh_project_layers()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(5)
        intro = QLabel("Find connected groups of adjacent polygons. Attribute matching is optional.")
        intro.setWordWrap(True); root.addWidget(intro)

        src = QGroupBox("1. Input data"); sl = QVBoxLayout(src); sl.setContentsMargins(8, 6, 8, 6); sl.setSpacing(4)
        modes = QHBoxLayout()
        self.project_radio, self.file_radio = QRadioButton("QGIS project layer"), QRadioButton("External SHP / GDB")
        self.project_radio.setChecked(True)
        self.project_radio.toggled.connect(self._mode_changed)
        modes.addWidget(self.project_radio); modes.addWidget(self.file_radio); sl.addLayout(modes)
        row = QHBoxLayout()
        self.layer_combo = QComboBox(); self.layer_combo.currentIndexChanged.connect(self._load_fields)
        row.addWidget(self.layer_combo, 1)
        refresh = QPushButton("Refresh"); refresh.clicked.connect(self.refresh_project_layers); row.addWidget(refresh)
        sl.addLayout(row)
        file_row = QHBoxLayout()
        self.path_edit = QLineEdit(); self.path_edit.setPlaceholderText("Select a .shp file or .gdb folder...")
        self.path_edit.textChanged.connect(self._open_external_path)
        file_row.addWidget(self.path_edit, 1)
        browse_shp = QPushButton("Browse SHP...")
        browse_shp.clicked.connect(self.browse_shapefile)
        file_row.addWidget(browse_shp)
        browse_gdb = QPushButton("Browse GDB...")
        browse_gdb.clicked.connect(self.browse_geodatabase)
        file_row.addWidget(browse_gdb)
        sl.addLayout(file_row)
        self.gdb_combo = QComboBox()
        self.gdb_combo.currentIndexChanged.connect(self._open_gdb_layer)
        self.gdb_combo.setVisible(False)
        sl.addWidget(self.gdb_combo)
        root.addWidget(src)

        attr = QGroupBox("2. Attribute matching"); al = QVBoxLayout(attr); al.setContentsMargins(8, 6, 8, 6); al.setSpacing(4)
        al.addWidget(QLabel("Select no fields for spatial-only analysis, or select fields whose values must match."))
        self.fields = QListWidget(); self.fields.setSelectionMode(QAbstractItemView.SingleSelection)
        self.fields.setMinimumHeight(112); self.fields.setMaximumHeight(112)
        self.fields.currentItemChanged.connect(self._update_value_button)
        al.addWidget(self.fields)
        value_row = QHBoxLayout()
        self.configure_values_btn = QPushButton("Configure values for selected field...")
        self.configure_values_btn.clicked.connect(self.configure_field_values)
        self.configure_values_btn.setEnabled(False)
        value_row.addWidget(self.configure_values_btn)
        self.value_status = QLabel("No field selected: spatial-only matching")
        self.value_status.setWordWrap(True)
        value_row.addWidget(self.value_status, 1)
        al.addLayout(value_row)
        opts = QHBoxLayout()
        self.ignore_case = QCheckBox("Ignore letter case"); self.ignore_case.setChecked(True)
        self.trim_space = QCheckBox("Trim leading/trailing whitespace"); self.trim_space.setChecked(True)
        opts.addWidget(self.ignore_case); opts.addWidget(self.trim_space); al.addLayout(opts)
        root.addWidget(attr)

        spatial = QGroupBox("3. Spatial criteria"); sf = QFormLayout(spatial); sf.setContentsMargins(8, 6, 8, 6); sf.setVerticalSpacing(3)
        self.min_length = QDoubleSpinBox(); self.min_length.setDecimals(6); self.min_length.setRange(0, 1e12)
        self.min_length.setToolTip("Uses map units of the input layer CRS.")
        sf.addRow("Minimum shared boundary length:", self.min_length)
        note = QLabel("Shared boundary segments are required. Point-only touches are ignored. The threshold uses input CRS map units.")
        note.setWordWrap(True); sf.addRow(note)
        self.include_isolated = QCheckBox("Include polygons with no matching adjacent polygon")
        self.include_isolated.setChecked(False)
        self.include_isolated.setToolTip(
            "When unchecked, only polygons with at least one qualifying adjacent polygon are included. "
            "When checked, eligible isolated polygons are also included as single-feature groups."
        )
        sf.addRow(self.include_isolated)
        root.addWidget(spatial)

        out = QGroupBox("4. Output"); of = QFormLayout(out); of.setContentsMargins(8, 6, 8, 6); of.setVerticalSpacing(3)
        of.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        of.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        of.setHorizontalSpacing(10)
        self.out_dir = QLineEdit()
        self.out_dir.setPlaceholderText("Choose output folder...")
        self.out_dir.setMinimumWidth(300)
        self.out_dir.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        obr = QHBoxLayout()
        obr.setContentsMargins(0, 0, 0, 0)
        obr.addWidget(self.out_dir, 1)
        ob = QPushButton("Browse...")
        ob.clicked.connect(self.browse_output)
        obr.addWidget(ob)
        of.addRow("Output folder:", obr)
        self.out_name = QLineEdit("adjacency_findings")
        self.out_name.setMinimumWidth(300)
        self.out_name.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        of.addRow("Output name:", self.out_name)
        self.individual = QCheckBox("Export individual polygon findings"); self.individual.setChecked(True)
        self.dissolved = QCheckBox("Export dissolved group geometries"); self.dissolved.setChecked(True)
        self.add_map = QCheckBox("Add output layers to QGIS project"); self.add_map.setChecked(True)
        of.addRow(self.individual); of.addRow(self.dissolved); of.addRow(self.add_map)
        root.addWidget(out)

        buttons = QHBoxLayout()
        self.run_btn = QPushButton("Run analysis"); self.run_btn.clicked.connect(self.run_analysis)
        close = QPushButton("Close"); close.clicked.connect(self.close)
        buttons.addWidget(self.run_btn); buttons.addWidget(close); root.addLayout(buttons)
        self.progress = QProgressBar(); self.progress.setFixedHeight(16); root.addWidget(self.progress)
        root.addWidget(QLabel("Processing log"))
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMaximumBlockCount(1000); self.log.setFixedHeight(75); root.addWidget(self.log, 1)
        self._mode_changed()

    def log_msg(self, msg): self.log.appendPlainText(msg)

    def refresh_project_layers(self):
        keep = self.layer_combo.currentData()
        self.layer_combo.blockSignals(True); self.layer_combo.clear()
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsVectorLayer) and layer.isValid() and QgsWkbTypes.geometryType(layer.wkbType()) == QgsWkbTypes.PolygonGeometry:
                self.layer_combo.addItem(layer.name(), layer.id())
        idx = self.layer_combo.findData(keep)
        if idx >= 0: self.layer_combo.setCurrentIndex(idx)
        self.layer_combo.blockSignals(False)
        if self.project_radio.isChecked(): self._load_fields()

    def _mode_changed(self, *_):
        project = self.project_radio.isChecked()
        self.layer_combo.setEnabled(project)
        self.path_edit.setEnabled(not project)
        self.gdb_combo.setEnabled(not project)
        self.gdb_combo.setVisible((not project) and self.gdb_combo.count() > 0)
        self._load_fields()

    def _current_layer(self):
        if self.project_radio.isChecked():
            lid = self.layer_combo.currentData()
            lyr = QgsProject.instance().mapLayer(lid) if lid else None
            return lyr if isinstance(lyr, QgsVectorLayer) and lyr.isValid() else None
        return self.external_layer if self.external_layer and self.external_layer.isValid() else None

    def _load_fields(self, *_):
        self.fields.clear()
        self.value_filters = {}
        layer = self._current_layer()
        if layer:
            for fld in layer.fields():
                item = QListWidgetItem(fld.name())
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
                item.setCheckState(Qt.Unchecked)
                self.fields.addItem(item)
        self._update_value_button()

    def _update_value_button(self, *_):
        item = self.fields.currentItem()
        self.configure_values_btn.setEnabled(item is not None)
        if item and item.text() in self.value_filters:
            count = len(self.value_filters[item.text()])
            self.value_status.setText("{} value(s) selected".format(count))
        elif item:
            self.value_status.setText("All values included by default")
        else:
            self.value_status.setText("No field selected: spatial-only matching")

    def configure_field_values(self):
        item = self.fields.currentItem()
        layer = self._current_layer()
        if item is None or layer is None:
            return
        field_name = item.text()
        values = {}
        for feature in layer.getFeatures():
            value = feature[field_name]
            key = normalize_value(value, self.ignore_case.isChecked(), self.trim_space.isChecked())
            values.setdefault(key, value)
        ordered = sorted(values.items(), key=lambda pair: "" if pair[1] is None else str(pair[1]).lower())

        dialog = QDialog(self)
        dialog.setWindowTitle("Select values - {}".format(field_name))
        dialog.resize(420, 480)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Only checked values will be included in the analysis."))
        value_list = QListWidget()
        current_filter = self.value_filters.get(field_name)
        for key, value in ordered:
            label = "<NULL>" if value is None else str(value)
            entry = QListWidgetItem(label)
            entry.setData(Qt.UserRole, key)
            entry.setFlags(entry.flags() | Qt.ItemIsUserCheckable)
            entry.setCheckState(Qt.Checked if current_filter is None or key in current_filter else Qt.Unchecked)
            value_list.addItem(entry)
        layout.addWidget(value_list, 1)
        actions = QHBoxLayout()
        select_all = QPushButton("Select All")
        deselect_all = QPushButton("Deselect All")
        select_all.clicked.connect(lambda: [value_list.item(i).setCheckState(Qt.Checked) for i in range(value_list.count())])
        deselect_all.clicked.connect(lambda: [value_list.item(i).setCheckState(Qt.Unchecked) for i in range(value_list.count())])
        actions.addWidget(select_all); actions.addWidget(deselect_all); layout.addLayout(actions)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec_() == QDialog.Accepted:
            self.value_filters[field_name] = [
                values[value_list.item(i).data(Qt.UserRole)]
                for i in range(value_list.count())
                if value_list.item(i).checkState() == Qt.Checked
            ]
            self._update_value_button()

    def _open_external_path(self, path):
        self.external_layer = None
        self.gdb_combo.blockSignals(True)
        self.gdb_combo.clear()
        self.gdb_combo.blockSignals(False)
        self.gdb_combo.setVisible(False)
        path = path.strip()

        if os.path.isfile(path) and path.lower().endswith(".shp"):
            lyr = QgsVectorLayer(path, os.path.splitext(os.path.basename(path))[0], "ogr")
            if lyr.isValid():
                self.external_layer = lyr
            else:
                self.log_msg("Unable to open Shapefile: {}".format(path))

        elif os.path.isdir(path) and path.lower().endswith(".gdb"):
            try:
                md = QgsProviderRegistry.instance().providerMetadata("ogr")
                details = md.querySublayers(path)
                self.gdb_combo.blockSignals(True)
                for detail in details:
                    self.gdb_combo.addItem(detail.name(), detail.uri())
                self.gdb_combo.blockSignals(False)

                if self.gdb_combo.count():
                    self.gdb_combo.setVisible(self.file_radio.isChecked())
                    self.gdb_combo.setCurrentIndex(0)
                    self._open_gdb_layer()
                else:
                    self.log_msg("No readable layers found in: {}".format(path))
            except Exception as exc:
                self.gdb_combo.blockSignals(False)
                self.log_msg("GDB layer listing failed: {}".format(exc))

        self._load_fields()

    def _open_gdb_layer(self, *_):
        uri = self.gdb_combo.currentData()
        self.external_layer = QgsVectorLayer(uri, self.gdb_combo.currentText(), "ogr") if uri else None
        if self.external_layer and not self.external_layer.isValid(): self.external_layer = None
        self._load_fields()

    def browse_shapefile(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Shapefile", self.path_edit.text().strip(),
            "Shapefile (*.shp)"
        )
        if path:
            self.file_radio.setChecked(True)
            self.path_edit.setText(path)
            self._open_external_path(path)

    def browse_geodatabase(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select File Geodatabase", self.path_edit.text().strip()
        )
        if path:
            self.file_radio.setChecked(True)
            self.path_edit.setText(path)
            self._open_external_path(path)

    def browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "Select output folder", "")
        if path: self.out_dir.setText(path)

    def _selected_fields(self):
        return [self.fields.item(i).text() for i in range(self.fields.count())
                if self.fields.item(i).checkState() == Qt.Checked]

    def _memory_layer(self, source, name, extra_fields):
        geom = QgsWkbTypes.displayString(source.wkbType())
        crs = source.crs().authid()
        layer = QgsVectorLayer("{}?crs={}".format(geom, crs), name, "memory")
        layer.dataProvider().addAttributes(list(source.fields()) + extra_fields)
        layer.updateFields()
        return layer

    def _save_shp(self, layer, path):
        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName = "ESRI Shapefile"; opts.fileEncoding = "UTF-8"
        res = QgsVectorFileWriter.writeAsVectorFormatV3(layer, path, QgsProject.instance().transformContext(), opts)
        if res[0] != QgsVectorFileWriter.NoError:
            raise RuntimeError("Shapefile export failed: {}".format(res[1]))

    def _export_individual(self, source, result, path):
        extras = [QgsField("GROUP_ID", QVariant.String, len=20), QgsField("SRC_FID", QVariant.LongLong),
                  QgsField("NEIGH_CNT", QVariant.Int), QgsField("STATUS", QVariant.String, len=12)]
        out = self._memory_layer(source, "individual_findings", extras)
        groupmap = {fid: g for g in result.groups for fid in g.feature_ids}
        originals = {f.id(): f for f in source.getFeatures(QgsFeatureRequest().setFilterFids(list(groupmap)))}
        new = []
        for fid, group in groupmap.items():
            original = originals.get(fid)
            if not original: continue
            f = QgsFeature(out.fields()); f.setGeometry(original.geometry())
            neighbor_count = group.neighbor_counts.get(fid, 0)
            status = "MATCH" if neighbor_count > 0 else "ISOLATED"
            f.setAttributes(original.attributes() + [group.group_id, int(fid), neighbor_count, status])
            new.append(f)
        out.dataProvider().addFeatures(new); out.updateExtents(); self._save_shp(out, path)

    def _export_dissolved(self, source, result, path):
        extras = [QgsField("GROUP_ID", QVariant.String, len=20), QgsField("MEMBER_CNT", QVariant.Int)]
        out = self._memory_layer(source, "dissolved_findings", extras)
        ids = [fid for g in result.groups for fid in g.feature_ids]
        originals = {f.id(): f for f in source.getFeatures(QgsFeatureRequest().setFilterFids(ids))}
        new = []
        for group in result.groups:
            members = [originals[fid] for fid in group.feature_ids if fid in originals]
            if not members: continue
            geom = QgsGeometry.unaryUnion([f.geometry() for f in members])
            if geom.isNull() or geom.isEmpty(): continue
            if QgsWkbTypes.isMultiType(out.wkbType()) and not geom.isMultipart(): geom.convertToMultiType()
            f = QgsFeature(out.fields()); f.setGeometry(geom)
            f.setAttributes(members[0].attributes() + [group.group_id, len(members)])
            new.append(f)
        out.dataProvider().addFeatures(new); out.updateExtents(); self._save_shp(out, path)

    def run_analysis(self):
        source = self._current_layer()
        if not source:
            QMessageBox.warning(self, "Input error", "Select a valid polygon layer or dataset."); return
        if QgsWkbTypes.geometryType(source.wkbType()) != QgsWkbTypes.PolygonGeometry:
            QMessageBox.warning(self, "Input error", "The selected layer is not polygon geometry."); return
        fields = self._selected_fields()
        folder = self.out_dir.text().strip()
        if not folder or not os.path.isdir(folder):
            QMessageBox.warning(self, "Output error", "Choose an existing output folder."); return
        if not self.individual.isChecked() and not self.dissolved.isChecked():
            QMessageBox.warning(self, "Output error", "Select at least one output type."); return
        prefix = re.sub(r"[^A-Za-z0-9_-]+", "_", self.out_name.text().strip()) or "adjacency_findings"
        self.run_btn.setEnabled(False); self.progress.setValue(0); self.log.clear()
        try:
            self.log_msg("Input: {}".format(source.name()))
            self.log_msg("Features: {}".format(source.featureCount()))
            self.log_msg("Matching mode: {}".format("Spatial-only (no attribute fields)" if not fields else "Attribute matching"))
            self.log_msg("Comparing fields: {}".format(", ".join(fields) if fields else "None"))
            allowed_values = {name: self.value_filters[name] for name in fields if name in self.value_filters}
            options = AdjacencyOptions(
                fields, self.ignore_case.isChecked(), self.trim_space.isChecked(),
                self.min_length.value(), allowed_values, self.include_isolated.isChecked()
            )
            result = detect_adjacent_groups(source, options)
            self.progress.setValue(80)
            self.log_msg("Qualifying adjacent pairs: {}".format(len(result.qualifying_pairs)))
            self.log_msg("Connected groups: {}".format(len(result.groups)))
            self.log_msg("Features in groups: {}".format(sum(g.member_count for g in result.groups)))
            isolated_count = sum(1 for g in result.groups if g.member_count == 1)
            self.log_msg("Isolated polygons included: {}".format(isolated_count))
            self.log_msg("Invalid geometries: {}".format(len(result.invalid_geometry_ids)))
            self.log_msg("Filtered out by attribute values: {}".format(result.filtered_feature_count))
            self.log_msg("Geometry operation errors: {}".format(result.geometry_error_count))
            paths = []
            if result.groups and self.individual.isChecked():
                p = os.path.join(folder, prefix + "_individual.shp"); self._export_individual(source, result, p); paths.append(p); self.log_msg("Created: " + p)
            if result.groups and self.dissolved.isChecked():
                p = os.path.join(folder, prefix + "_dissolved.shp"); self._export_dissolved(source, result, p); paths.append(p); self.log_msg("Created: " + p)
            if self.add_map.isChecked():
                for p in paths:
                    lyr = QgsVectorLayer(p, os.path.splitext(os.path.basename(p))[0], "ogr")
                    if lyr.isValid(): QgsProject.instance().addMapLayer(lyr)
            self.progress.setValue(100)
            QMessageBox.information(self, "Analysis completed",
                "Groups found: {}\nQualifying pairs: {}\nInvalid geometries: {}\nOutput files: {}".format(
                    len(result.groups), len(result.qualifying_pairs), len(result.invalid_geometry_ids), len(paths)))
        except Exception as exc:
            self.log_msg("ERROR: {}".format(exc)); self.log_msg(traceback.format_exc())
            QMessageBox.critical(self, "Analysis failed", str(exc))
        finally:
            self.run_btn.setEnabled(True)
