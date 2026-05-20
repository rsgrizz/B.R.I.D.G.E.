# Created by: Randy Grizzelli
# Email: grizzellir@gmail.com
# GitHub: https://github.com/rsgrizz
# Version: v.3
# Date: 5/18/2026
# Purpose: Static registry defining the graph of supported and experimental format conversions.

from app.core.models import FileFormat, ConversionEdge

class ConversionRegistry:
    """Manages the static set of supported, experimental, and direct conversion edges."""

    _edges = [
        # Native QEMU Conversions (RAW to Virtual Disks)
        ConversionEdge(
            source=FileFormat.RAW,
            target=FileFormat.VMDK,
            backend_tool="qemu-img",
            command_template_tokens=["qemu-img", "convert", "-f", "raw", "-O", "vmdk", "{input}", "{output}"],
            experimental=False,
            notes="Convert RAW/DD image to VMDK virtual disk.",
            weight=1.0
        ),
        ConversionEdge(
            source=FileFormat.RAW,
            target=FileFormat.VHD,
            backend_tool="qemu-img",
            command_template_tokens=["qemu-img", "convert", "-f", "raw", "-O", "vpc", "{input}", "{output}"],
            experimental=False,
            notes="Convert RAW/DD image to legacy VHD (vpc).",
            weight=1.0
        ),
        ConversionEdge(
            source=FileFormat.RAW,
            target=FileFormat.VHDX,
            backend_tool="qemu-img",
            command_template_tokens=["qemu-img", "convert", "-f", "raw", "-O", "vhdx", "{input}", "{output}"],
            experimental=False,
            notes="Convert RAW/DD image to VHDX virtual disk.",
            weight=1.0
        ),
        ConversionEdge(
            source=FileFormat.RAW,
            target=FileFormat.QCOW2,
            backend_tool="qemu-img",
            command_template_tokens=["qemu-img", "convert", "-f", "raw", "-O", "qcow2", "{input}", "{output}"],
            experimental=False,
            notes="Convert RAW/DD image to QCOW2 virtual disk.",
            weight=1.0
        ),
        
        # Native QEMU Conversions (Virtual Disks to RAW)
        ConversionEdge(
            source=FileFormat.VMDK,
            target=FileFormat.RAW,
            backend_tool="qemu-img",
            command_template_tokens=["qemu-img", "convert", "-f", "vmdk", "-O", "raw", "{input}", "{output}"],
            experimental=False,
            notes="Convert VMDK virtual disk to RAW image.",
            weight=1.0
        ),
        ConversionEdge(
            source=FileFormat.VHD,
            target=FileFormat.RAW,
            backend_tool="qemu-img",
            command_template_tokens=["qemu-img", "convert", "-f", "vpc", "-O", "raw", "{input}", "{output}"],
            experimental=False,
            notes="Convert legacy VHD (vpc) virtual disk to RAW image.",
            weight=1.0
        ),
        ConversionEdge(
            source=FileFormat.VHDX,
            target=FileFormat.RAW,
            backend_tool="qemu-img",
            command_template_tokens=["qemu-img", "convert", "-f", "vhdx", "-O", "raw", "{input}", "{output}"],
            experimental=False,
            notes="Convert VHDX virtual disk to RAW image.",
            weight=1.0
        ),
        ConversionEdge(
            source=FileFormat.QCOW2,
            target=FileFormat.RAW,
            backend_tool="qemu-img",
            command_template_tokens=["qemu-img", "convert", "-f", "qcow2", "-O", "raw", "{input}", "{output}"],
            experimental=False,
            notes="Convert QCOW2 virtual disk to RAW image.",
            weight=1.0
        ),
        
        # Native QEMU Virtual Disk conversions (Direct)
        ConversionEdge(
            source=FileFormat.VMDK,
            target=FileFormat.VHD,
            backend_tool="qemu-img",
            command_template_tokens=["qemu-img", "convert", "-f", "vmdk", "-O", "vpc", "{input}", "{output}"],
            experimental=False,
            notes="Direct conversion VMDK to VHD.",
            weight=1.0
        ),
        ConversionEdge(
            source=FileFormat.VMDK,
            target=FileFormat.VHDX,
            backend_tool="qemu-img",
            command_template_tokens=["qemu-img", "convert", "-f", "vmdk", "-O", "vhdx", "{input}", "{output}"],
            experimental=False,
            notes="Direct conversion VMDK to VHDX.",
            weight=1.0
        ),
        ConversionEdge(
            source=FileFormat.VMDK,
            target=FileFormat.QCOW2,
            backend_tool="qemu-img",
            command_template_tokens=["qemu-img", "convert", "-f", "vmdk", "-O", "qcow2", "{input}", "{output}"],
            experimental=False,
            notes="Direct conversion VMDK to QCOW2.",
            weight=1.0
        ),
        ConversionEdge(
            source=FileFormat.VHD,
            target=FileFormat.VMDK,
            backend_tool="qemu-img",
            command_template_tokens=["qemu-img", "convert", "-f", "vpc", "-O", "vmdk", "{input}", "{output}"],
            experimental=False,
            notes="Direct conversion VHD to VMDK.",
            weight=1.0
        ),
        ConversionEdge(
            source=FileFormat.VHD,
            target=FileFormat.QCOW2,
            backend_tool="qemu-img",
            command_template_tokens=["qemu-img", "convert", "-f", "vpc", "-O", "qcow2", "{input}", "{output}"],
            experimental=False,
            notes="Direct conversion VHD to QCOW2.",
            weight=1.0
        ),
        ConversionEdge(
            source=FileFormat.VHDX,
            target=FileFormat.VMDK,
            backend_tool="qemu-img",
            command_template_tokens=["qemu-img", "convert", "-f", "vhdx", "-O", "vmdk", "{input}", "{output}"],
            experimental=False,
            notes="Direct conversion VHDX to VMDK.",
            weight=1.0
        ),
        ConversionEdge(
            source=FileFormat.VHDX,
            target=FileFormat.QCOW2,
            backend_tool="qemu-img",
            command_template_tokens=["qemu-img", "convert", "-f", "vhdx", "-O", "qcow2", "{input}", "{output}"],
            experimental=False,
            notes="Direct conversion VHDX to QCOW2.",
            weight=1.0
        ),
        ConversionEdge(
            source=FileFormat.QCOW2,
            target=FileFormat.VMDK,
            backend_tool="qemu-img",
            command_template_tokens=["qemu-img", "convert", "-f", "qcow2", "-O", "vmdk", "{input}", "{output}"],
            experimental=False,
            notes="Direct conversion QCOW2 to VMDK.",
            weight=1.0
        ),
        ConversionEdge(
            source=FileFormat.QCOW2,
            target=FileFormat.VHD,
            backend_tool="qemu-img",
            command_template_tokens=["qemu-img", "convert", "-f", "qcow2", "-O", "vpc", "{input}", "{output}"],
            experimental=False,
            notes="Direct conversion QCOW2 to VHD.",
            weight=1.0
        ),
        ConversionEdge(
            source=FileFormat.QCOW2,
            target=FileFormat.VHDX,
            backend_tool="qemu-img",
            command_template_tokens=["qemu-img", "convert", "-f", "qcow2", "-O", "vhdx", "{input}", "{output}"],
            experimental=False,
            notes="Direct conversion QCOW2 to VHDX.",
            weight=1.0
        ),

        # Libewf Native E01 Export
        ConversionEdge(
            source=FileFormat.E01,
            target=FileFormat.RAW,
            backend_tool="ewfexport",
            command_template_tokens=["ewfexport", "-t", "{output_no_ext}", "-f", "raw", "{input}"],
            experimental=False,
            notes="Stable EWF export to RAW image.",
            weight=1.0
        ),
        
        # Experimental paths
        ConversionEdge(
            source=FileFormat.DMG,
            target=FileFormat.RAW,
            backend_tool="qemu-img",
            command_template_tokens=["qemu-img", "convert", "-f", "dmg", "-O", "raw", "{input}", "{output}"],
            experimental=True,
            notes="Experimental DMG to RAW conversion.",
            weight=10.0
        ),
        ConversionEdge(
            source=FileFormat.EX01,
            target=FileFormat.RAW,
            backend_tool="ewfexport",
            command_template_tokens=["ewfexport", "-t", "{output_no_ext}", "-f", "raw", "{input}"],
            experimental=True,
            notes="Experimental EWF2 export to RAW image.",
            weight=10.0
        ),
    ]

    @classmethod
    def get_supported_edges(cls) -> list[ConversionEdge]:
        """Returns all supported transition edges."""
        return cls._edges
