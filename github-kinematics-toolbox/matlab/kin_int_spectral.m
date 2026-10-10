function y = kin_int_spectral(a, dt, order, fc, taper)
%KIN_INT_SPECTRAL FFT integration with a high-pass corner fc (Hz).
%   taper : Tukey taper fraction per end (default 0.05).  The record is not
%   periodic, so without it the wrap-around discontinuity leaks across the
%   whole spectrum; it costs about 0.2 percentage points of accuracy here.
if nargin < 5 || isempty(taper), taper = 0.05; end
a = a(:);  n = numel(a);  t = (0:n-1)'*dt;
a = a - polyval(polyfit(t, a, 1), t);
w = ones(n,1);
if taper > 0
    al = 2*taper;  xx = (0:n-1)'/(n-1);
    i1 = xx < al/2;       w(i1) = 0.5*(1 + cos(2*pi/al*(xx(i1) - al/2)));
    i2 = xx > 1 - al/2;   w(i2) = 0.5*(1 + cos(2*pi/al*(xx(i2) - 1 + al/2)));
    a = a .* w;
end
A = fft(a);
k = [0:floor(n/2), -ceil(n/2)+1:-1]';
om = 2*pi*k/(n*dt);  ao = abs(om);
H = double(ao > 0);
if nargin >= 4 && ~isempty(fc)
    oc = 2*pi*fc;  lo = 0.5*oc;  b = ao > lo & ao <= oc;
    H(b) = 0.5*(1 - cos(pi*(ao(b)-lo)/(oc-lo)));
    H(ao <= lo) = 0;
end
X = zeros(n,1);  nz = ao > 0;
X(nz) = A(nz) .* H(nz) ./ (1i*om(nz)).^order;
y = real(ifft(X));
if taper > 0, y = y ./ max(w, 1e-3); end
end
