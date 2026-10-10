function fb = kin_signal_band(x, dt, factor, nperseg)
%KIN_SIGNAL_BAND Highest frequency (Hz) where the PSD exceeds factor x the noise plateau.
%
%   fb = kin_signal_band(x, dt, factor, nperseg)     defaults: factor 3, nperseg 256
%
%   Welch PSD (periodic Hann, 50 % overlap, linear detrend per segment --
%   scipy.signal.welch defaults), noise plateau = median over 0.40-0.49 fs, as
%   in kin_noisevar.  Short segments average enough periodograms that a factor
%   of 3 is not crossed by noise alone.  For several columns the maximum is
%   returned.  Used by kin_delay_project as a guard against noise directions.

if nargin < 3 || isempty(factor), factor = 3; end
if nargin < 4 || isempty(nperseg), nperseg = 256; end
if isvector(x), x = x(:); end
fb = 0;
for j = 1:size(x,2)
    [f, P] = welch_lin(x(:,j), dt, min(size(x,1), nperseg));
    m = f >= 0.40/dt & f <= 0.49/dt;
    if ~any(m), m = f >= 0.8*f(end); end
    k = find(P > factor*median(P(m)), 1, 'last');
    if isempty(k), fj = f(end); else, fj = f(k); end
    fb = max(fb, fj);
end
end

function [f, P] = welch_lin(y, dt, nps)
y = y - mean(y);  n = numel(y);  step = nps - floor(nps/2);
w = 0.5 - 0.5*cos(2*pi*(0:nps-1)'/nps);               % periodic Hann (scipy)
tt = (0:nps-1)';  A = [tt ones(nps,1)];
nseg = floor((n - nps)/step) + 1;  P = 0;
for s = 0:nseg-1
    seg = y(s*step + (1:nps));
    seg = seg - A*(A\seg);                            % linear detrend
    Y = fft(seg.*w);
    P = P + abs(Y(1:floor(nps/2)+1)).^2;
end
P = P / (nseg * sum(w.^2) / dt);
if mod(nps,2) == 0, P(2:end-1) = 2*P(2:end-1); else, P(2:end) = 2*P(2:end); end
f = (0:floor(nps/2))' / (nps*dt);
end
