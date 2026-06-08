# The thesis template loads fontspec, which requires XeLaTeX or LuaLaTeX.
# pdf_mode = 5 makes `latexmk` (with no engine flag) build with xelatex,
# so `latexmk main.tex` works and pdflatex's fatal fontspec error is avoided.
$pdf_mode = 5;
