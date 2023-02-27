# pyffy

Small tool for correction of lens vignetting and color cast.



This application was inspired by following facts:

- the only application I know that can correct various casts in raw image and write corrected image to raw DNG is Adobe Lightroom. Also, there is an application called CornerFix, but its approach to correction is not suitable in most cases
- UX of Lightroom flat field correction is ugly and annoying
- Lightroom costs money even if the flat field (FF) correction is the only feature you need
- (the most important one) Lightroom's FF correction feature has a long-lasting bug, that Adobe refuses to fix: https://community.adobe.com/t5/lightroom-classic-discussions/flatfield-correction-behavior/m-p/12948584#M274777



Credits go to DPReview forum member Horshack https://www.dpreview.com/forums/thread/4566327



### Requirements:

- numpy
- opencv
- (optional) send2trash



### Features:

- separate control of the correction intensity for luminance and color casts
- automatic search for appropriate FF reference file in the given FF files folder
- adjustable radius of gaussian blur used to exclude dust (pyffy is not intended for dust removal) from correction
- three working modes:
  - one pass, many references: default. In this mode pyffy searches for appropriate FF file
  - one pass, one reference: may be useful to correct images taken with manual lenses, i.e. without focal length and F-number recorded
  - two passes: may be useful also for shots taken with manual lenses, or to override global correction settings
- can write corrected files to the output folder or overwrite source files
- supports bayer, linear (demosaiced) and monochrome files



### Limitations

- only non-compressed DNG is supported
- multi image (pixel shift, for example) DNG is not supported
- automatic match based on focusing distance (not focal length!) is impossible. So if some lens cast differs significantly when focused to infinity and MDF, two pass mode should be used



On the first launch pyffy creates `settings.json` in its folder, and exits, because at least one entry must be filled, see below.



### Settings explained

```python
useMultithreading
```

Using multithreading speeds up processing a lot, but if multithreading is undesirable for some reason it can be disabled.



```python
referenceFilesFolderRoot
```

Root folder to look for reference files. When `settings.json` is created this entry is empty, and must be edited to point to the folder with reference files, otherwise only `one pass, one reference` mode can be used. If this entry is not empty pyffy looks for `referenceDB.json` inside it. If it is absent - pyffy looks for all DNG files in the tree starting from this folder, and fills `referenceDB.json` with required metadata. If for some reason this DB should be updated - just delete `referenceDB.json` and it will be recreated on the next launch.



```python
overwriteSourceFile
```

If true pyffy will write corrected result to the source file. Be very, VERY careful with it, please.



```python
askForConfirmationOnStartIfOverwritingOriginalsIsEnabled
```

Just one more confirmation before overwriting source files.



```python
pathForProcessedFiles
```

Must be set if `overwriteSourceFile = false`



```python
luminanceCorrectionIntensity
```

and

```python
colorCorrectionIntensity
```

Working range is from 0.0 (no correction) to 1.0 (full correction). Negative values will be treated as 0.0, values higher than 1.0 - as 1.0



```
advIgnoreLensTag
```

`Lens` tag does not always contain correct value, for example old PhaseOne DB fills it as `-- mm f/--`, so it should not be included as rule to the reference file matcher.



```python
advLimitToWhiteLevels
```

If **`true`** corrected file will be trimmed to the range between `BlackLevel` and `WhiteLevel` (channel wise) declared in the exif. Note that `WhiteLevel` is not always set to the real maximum level written by specific camera. For example, Canon 5D mark III declares `WhiteLevel` as 15000, but real overexposured pixels can reach 15800+ (without `BlackLevel` subtracted). So after correction overexposure can start a bit earlier than before correction. When **`false`** values are limited by 65535 (with `BlackLevel` added). Most converters will just ignore this unusual values and treat it as overexposure, but some may produce strange results in such case.



```python
advGaussianFilterSigma
```

"Radius" of gaussian blur applied to the reference file. Blurring is used to exclude sensor noise and dust from correction. Too low value leads to dust inclusion to correction, i.e. to white spots on corrected image. Too high value leads to too slow processing, and possibly to too high blurring of lens\sensor imperfections.



```python
advMaxAllowedFocalLengthDifferencePercent
```

Tells reference file matcher how much reference file focal length may differ from current processed file focal length. Useful for zoom lenses.



```python
advMaxAllowedFNumberDifferenceStops
```

Tells reference file matcher how much reference file F-number may differ from current processed file F-number. Useful when reference files for specific F-number is not available, i.e. if reference files contain only full stops (2.8, 4.0, 5.6 ...), and current file is shot with F-number 3.2 or 5.0.



```python
advUpdateDngSoftwareTagToAvoidOverprocessing
```

If **`true`** `, pyffy` is added to the Software tag. When pyffy reads file for processing it looks for this text and skips file if found to avoid processing file more than once.



### Disclaimer

Application is provided as is without any guarantees. I am not and will not be responsible for any damage to your files it can make. If you have some file that is not described in the **Limitations** section above but can not be processed by pyffy - feel free to open issue, I'll try to investigate the cause and fix it, but again no guarantee is given.