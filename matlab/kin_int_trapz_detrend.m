function y = kin_int_trapz_detrend(a, dt, order, poly, hp)
%KIN_INT_TRAPZ_DETREND Cumulative trapezoid with baseline correction at each stage.
%
%   y = kin_int_trapz_detrend(a, dt, order, poly, hp)
%
%   The classical strong-motion recipe (Boore): remove a degree-`poly`
%   polynomial, optionally high-pass, integrate; repeat `order` times; correct
%   once more at the end.  hp (Hz) adds a zero-phase 4th-order Butterworth
%   high-pass at each stage, which is what actually controls the drift.
%
%   Included as the baseline to beat.  On the benchmark it is the least
%   accurate and the most brittle of the integrators (usable hp window about
%   0.1 decade wide).  Prefer kin_int_tikhonov or kin_smooth.
%
%   The zero-phase pass reproduces scipy.signal.filtfilt's defaults (odd
%   extension, 3*max(len(b),len(a)) samples, steady-state initial conditions)
%   rather than MATLAB's filtfilt (3*(nfilt-1) samples), so the output
%   matches the Python reference over the whole record, ends included.
%   Requires the Signal Processing Toolbox (butter).

if nargin < 3 || isempty(order), order = 1; end
if nargin < 4 || isempty(poly), poly = 1; end
if nargin < 5, hp = []; end
y = a(:);  n = numel(y);  t = (0:n-1)'*dt;
if ~isempty(hp), [b, aa] = butter(4, hp/(0.5/dt), 'high'); end
for s = 1:order
    y = y - polyval(polyfit(t, y, poly), t);
    if ~isempty(hp), y = filtfilt_scipy(b, aa, y); end
    y = cumtrapz(y)*dt;
end
y = y - polyval(polyfit(t, y, poly), t);
if ~isempty(hp), y = filtfilt_scipy(b, aa, y); end
end

function y = filtfilt_scipy(b, a, x)
%FILTFILT_SCIPY Zero-phase filter with scipy.signal.filtfilt default padding.
b = b(:)'/a(1);  a = a(:)'/a(1);
nf = max(numel(a), numel(b));
b(end+1:nf) = 0;  a(end+1:nf) = 0;
np = 3*nf;
if numel(x) <= np, error('kin_int_trapz_detrend: record too short for filtfilt'); end
ext = [2*x(1) - x(np+1:-1:2); x; 2*x(end) - x(end-1:-1:end-np)];
% steady-state initial conditions (scipy.signal.lfilter_zi)
A  = [-a(2:end)', [eye(nf-2); zeros(1,nf-2)]];
zi = (eye(nf-1) - A) \ (b(2:end)' - a(2:end)'*b(1));
y  = filter(b, a, ext, zi*ext(1));
y  = flipud(y);
y  = filter(b, a, y, zi*y(1));
y  = flipud(y);
y  = y(np+1:end-np);
end
