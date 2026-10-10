function y = kin_diff_spectral(x, dt, order, fc)
%KIN_DIFF_SPECTRAL FFT differentiation with an optional low-pass at fc (Hz).
%   Exact for periodic bandlimited data; degrades badly near the record ends.
x = x(:);  n = numel(x);  t = (0:n-1)'*dt;
p = polyfit(t, x, 1);  xd = x - polyval(p, t);
X = fft(xd);
k = [0:floor(n/2), -ceil(n/2)+1:-1]';
om = 2*pi*k/(n*dt);
if nargin >= 4 && ~isempty(fc)
    oc = 2*pi*fc;  ao = abs(om);  roll = ones(n,1);
    lo = 0.8*oc;  b = ao > lo & ao <= oc;
    roll(b) = 0.5*(1 + cos(pi*(ao(b)-lo)/(oc-lo)));
    roll(ao > oc) = 0;
    X = X .* roll;
end
y = real(ifft(X .* (1i*om).^order));
if order == 1, y = y + p(1); end
end
