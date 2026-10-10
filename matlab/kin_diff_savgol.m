function y = kin_diff_savgol(x, dt, order, fc, window, polyorder)
%KIN_DIFF_SAVGOL Savitzky-Golay derivative, base MATLAB (no sgolay needed).
%   Window from the -3 dB rule fc*dt ~ (polyorder+1)/(3.2*M-4.6)  [Schafer 2011].
if nargin < 6 || isempty(polyorder), polyorder = 3; end
x = x(:);  n = numel(x);
if nargin < 5 || isempty(window)
    M = ((polyorder+1)/(fc*dt) + 4.6)/3.2;
    window = ceil(2*M+1);
end
window = max(polyorder+2, window);
if mod(window,2) == 0, window = window + 1; end
M = (window-1)/2;
z = (-M:M)';
A = z .^ (0:polyorder);
C = pinv(A);                            % rows: polynomial coefficients
c = C(order+1,:)' * factorial(order) / dt^order;
y = conv(x, flipud(c), 'same');
% one-sided fits at the ends
for i = [1:M, n-M+1:n]
    lo = max(1, i-M);  hi = min(n, i+M);
    zz = ((lo:hi)' - i);
    Ai = zz .^ (0:polyorder);
    ci = pinv(Ai);
    y(i) = ci(order+1,:) * x(lo:hi) * factorial(order) / dt^order;
end
end
