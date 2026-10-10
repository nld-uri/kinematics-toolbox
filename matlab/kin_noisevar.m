function s2 = kin_noisevar(y, dt, band)
%KIN_NOISEVAR Measurement-noise variance from the white PSD plateau near Nyquist.
%   Welch estimate written out in base MATLAB (no Signal Processing Toolbox).
if nargin < 3, band = [0.40 0.49]; end
y = y(:) - mean(y(:));
n = numel(y);  nps = min(n, 4096);  nov = floor(nps/2);  step = nps - nov;
w = 0.5 - 0.5*cos(2*pi*(0:nps-1)'/(nps-1));          % Hann
U = sum(w.^2)/nps;  P = 0;  cnt = 0;
for s = 1:step:(n-nps+1)
    seg = y(s:s+nps-1);
    p = polyfit((1:nps)', seg, 1);  seg = seg - polyval(p, (1:nps)');
    Y = fft(seg .* w);
    P = P + abs(Y(1:floor(nps/2)+1)).^2;  cnt = cnt + 1;
end
P = P / (cnt * nps * U / dt);  P(2:end-1) = 2*P(2:end-1);
f = (0:floor(nps/2))' / (nps*dt);
m = f >= band(1)/dt & f <= band(2)/dt;
if ~any(m), m = f >= 0.8*f(end); end
s2 = median(P(m)) * (0.5/dt);
end
