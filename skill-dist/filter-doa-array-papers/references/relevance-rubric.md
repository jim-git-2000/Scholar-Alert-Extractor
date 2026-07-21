# DOA and array relevance rubric

Judge the paper's primary technical contribution, not isolated terminology. A paper is relevant
when DOA/direction finding or array signal processing is a substantive problem, model, method,
experiment, or evaluation target.

## Include as relevant

### `core-doa`

- Direction/angle/bearing of arrival estimation or direction finding.
- Azimuth/elevation estimation, one-dimensional or multi-dimensional DOA.
- Near-field or far-field source localization where angular estimation is substantive.
- Wideband, narrowband, coherent, noncircular, nested, sparse, coprime, moving, rotating, planar,
  circular, conformal, distributed, or vector-sensor DOA methods.
- MUSIC, ESPRIT, maximum likelihood, sparse recovery, atomic norm, covariance fitting, tensor,
  Bayesian, deep-learning, or gridless methods whose evaluated target includes DOA.

### `array-signal-processing`

- A primary method for multichannel spatial inference using antenna, acoustic, microphone, radar,
  sonar, seismic, or other sensor arrays.
- Source enumeration, covariance/coarray processing, spatial smoothing, coherent-source handling,
  or array manifold processing explicitly situated in a DOA/localization pipeline.
- Beamforming or spatial spectrum estimation when direction estimation, localization, source
  separation by direction, or array inference is a central objective.

### `array-design-calibration`

- Array geometry, sparse-array placement, virtual/coarray aperture, sensor selection, or array
  motion designed or evaluated for DOA/localization performance.
- Mutual coupling, gain/phase error, sensor-position error, array-manifold mismatch, calibration,
  or robustness methods that directly enable array parameter estimation.
- CRB, identifiability, resolution, degrees of freedom, or ambiguity analysis explicitly for DOA or
  spatial array estimation.

### `joint-spatial-estimation`

- Joint angle-delay, angle-Doppler, range-angle, angle-frequency, localization-communication, or
  tracking problems where angular/array estimation is a substantial output rather than incidental
  metadata.
- MIMO radar, ISAC, channel sounding, or wireless sensing papers with a genuine angle-estimation or
  array-localization contribution.

## Exclude

Use `excluded` / `out-of-scope` when the primary contribution is:

- Generic machine learning, optimization, image processing, control, or communications with no
  sensor/antenna-array spatial inference.
- A data structure, software array, biological array, detector pixel array, or an occurrence of the
  word “array” unrelated to array signal processing.
- Antenna element, metasurface, phased-array hardware, feed network, radiation pattern, or antenna
  synthesis work that does not address DOA/localization or array signal inference.
- Beamforming only for link throughput, coverage, interference suppression, or waveform delivery,
  with no direction estimation/localization contribution.
- Single-sensor localization or tracking with no angular observation model or array processing.
- A survey or application that merely mentions DOA/arrays in background text but contributes to a
  different technical problem.

Do not exclude merely because the title omits “DOA”. The snippet can establish a substantive array
estimation method. Conversely, do not include merely because an alert name or snippet contains a
saved-search keyword.

## Use review sparingly

Choose `review` / `borderline` only when available metadata leaves the primary contribution unclear,
for example:

- The title says “localization” but does not reveal whether an array or angular estimator is used.
- A beamforming or array-calibration title lacks enough context to distinguish communications-only
  use from spatial inference.
- An antenna-array paper might contain a DOA experiment, but the title/snippet does not say.
- The snippet is truncated or absent, so the Excel metadata cannot establish the paper's scope.

Do not use `review` simply because a method is unfamiliar. Infer from the objective and evaluation
target stated in the available Excel fields.

## Evidence and reasons

Reasons must state the decisive technical relationship. Good examples:

- `relevant`: “以稀疏阵列协方差补全实现无网格二维 DOA 估计，角度估计是核心输出。”
- `excluded`: “研究相控阵馈电网络与辐射效率，未涉及入射方向估计或阵列信号推断。”
- `review`: “题名仅说明室内定位，摘要片段缺失，无法确认是否采用阵列角度观测。”

Avoid reasons such as “contains DOA”, “looks relevant”, or “not related”.
