Remove-Item -Recurse -Force sort_testing/*

New-Item -ItemType Directory -Force -Path sort_testing
New-Item -ItemType File -Force -Path sort_testing/friday.txt
New-Item -ItemType File -Force -Path sort_testing/pro.mkv
New-Item -ItemType File -Force -Path sort_testing/something.txt
New-Item -ItemType File -Force -Path sort_testing/that.pdf
New-Item -ItemType File -Force -Path sort_testing/vacation.mp4
New-Item -ItemType Directory -Force -Path sort_testing/Folderwithfiles
New-Item -ItemType File -Force -Path sort_testing/Folderwithfiles/boot.avi
New-Item -ItemType File -Force -Path sort_testing/Folderwithfiles/container.docx
New-Item -ItemType File -Force -Path sort_testing/Folderwithfiles/file.jpg