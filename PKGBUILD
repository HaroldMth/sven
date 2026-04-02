# Maintainer: HANS TECH <open-source@hanstech.dev>
pkgname=sven-bin
pkgver=1.0.0
pkgrel=1
pkgdesc="Sven Package Manager for Seven OS (LFS) - PyInstaller Binary"
arch=('x86_64')
url="https://github.com/haroldmth/sven"
license=('GPL3')
depends=('git' 'gnupg' 'curl' 'tar' 'zstd')
provides=('sven')
conflicts=('sven' 'sven-git')
source=("sven-x86_64-linux::https://github.com/haroldmth/sven/releases/download/v${pkgver}/sven-x86_64-linux")
sha256sums=('SKIP') # Use actual sha256 in production or use workflow to inline it

package() {
    # Install binary
    install -Dm755 "${srcdir}/sven-x86_64-linux" "${pkgdir}/usr/local/bin/sven"
    
    # Create required directory structure
    install -dm755 "${pkgdir}/var/lib/sven/installed"
    install -dm755 "${pkgdir}/var/lib/sven/sync"
    install -dm755 "${pkgdir}/var/lib/sven/aur_cache"
    install -dm755 "${pkgdir}/var/lib/sven/snapshots"
    install -dm755 "${pkgdir}/var/cache/sven/pkgs"
    install -dm755 "${pkgdir}/var/cache/sven/aur"
    install -dm755 "${pkgdir}/var/log/sven"
    install -dm755 "${pkgdir}/etc/sven/initscripts"
    install -dm755 "${pkgdir}/tmp/sven/aur"

    # Default config
    cat > "${srcdir}/sven.conf" << 'EOF'
[general]
install_root      = /
cache_dir         = /var/cache/sven
db_path           = /var/lib/sven
init_system       = sysvinit

[repos]
use_official      = true
use_aur           = true
aur_review        = prompt

[build]
parallel_jobs     = 4
keep_cache        = true

[download]
parallel_downloads = 5
mirror             = auto

[upgrade]
ignored_packages  =
held_packages     =
EOF
    install -Dm644 "${srcdir}/sven.conf" "${pkgdir}/etc/sven/sven.conf"
}
