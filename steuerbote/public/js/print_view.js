// Drucken in the print view of a Steuerbote format prints the PDF of the PDF generator, the one the button PDF
// downloads, with Frappe's own print_pdf: the browser's print of the HTML of the print view has no running head and
// foot and no page numbers. A print server, a printer mapped for QZ Tray and raw printing stay with Frappe, and so
// does every format of another module. Frappe adds this file to the page script of the print view after its own
// (page_js in hooks.py), which may run it twice; another app may wrap printit the same way, each keeping the one
// before it.

(() => {
	const PrintView = frappe.ui.form.PrintView;
	if (!PrintView || PrintView.prototype.steuerbote_printit) {
		return;
	}
	PrintView.prototype.steuerbote_printit = PrintView.prototype.printit;

	PrintView.prototype.prints_steuerbote_pdf = function () {
		const format = this.get_print_format();
		return (
			format.module === "Steuerbote" &&
			!format.raw_printing &&
			!cint(this.print_settings.enable_print_server) &&
			!this.get_mapped_printer().length
		);
	};

	PrintView.prototype.printit = function () {
		return this.prints_steuerbote_pdf() ? this.print_pdf() : this.steuerbote_printit();
	};
})();
