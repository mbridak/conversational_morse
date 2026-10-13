"""Small modal dialogs used by the main window."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..config import StationConfig


class StationDialog(QDialog):
    """Collect the operator's own station details."""

    def __init__(self, station: StationConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Station setup")
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.callsign = QLineEdit(station.callsign)
        self.name = QLineEdit(station.name)
        self.qth = QLineEdit(station.qth)
        self.rig = QLineEdit(station.rig)
        self.power = QLineEdit(station.power)
        self.antenna = QLineEdit(station.antenna)
        self.key_type = QLineEdit(station.key_type)
        self.weather = QLineEdit(station.weather)

        self.age = QSpinBox()
        self.age.setRange(0, 120)
        self.age.setValue(station.age)
        self.years_licensed = QSpinBox()
        self.years_licensed.setRange(0, 100)
        self.years_licensed.setValue(station.years_licensed)
        self.temperature_f = QSpinBox()
        self.temperature_f.setRange(-80, 140)
        self.temperature_f.setValue(station.temperature_f)

        form.addRow("Callsign:", self.callsign)
        form.addRow("Name:", self.name)
        form.addRow("QTH:", self.qth)
        form.addRow("Rig:", self.rig)
        form.addRow("Power:", self.power)
        form.addRow("Antenna:", self.antenna)
        form.addRow("Key:", self.key_type)
        form.addRow("Weather:", self.weather)
        form.addRow("Age:", self.age)
        form.addRow("Years licensed:", self.years_licensed)
        form.addRow("Temperature (F):", self.temperature_f)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def station(self) -> StationConfig:
        """Build a validated :class:`StationConfig` from the fields."""
        return StationConfig(
            callsign=self.callsign.text(),
            name=self.name.text(),
            qth=self.qth.text(),
            rig=self.rig.text(),
            power=self.power.text(),
            antenna=self.antenna.text(),
            key_type=self.key_type.text(),
            weather=self.weather.text(),
            age=self.age.value(),
            years_licensed=self.years_licensed.value(),
            temperature_f=self.temperature_f.value(),
        )
