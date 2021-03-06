import asciitable
import matplotlib.pyplot as plt
import numpy as np
from Ska.Matplotlib import plot_cxctime, cxctime2plotdate
import Ska.engarchive.fetch_eng as fetch
from Chandra.Time import DateTime

from bad_times import bad_times

plt.rc('legend', fontsize=10)

def plot_pitches_any_kalman(out, angle_err_lim=8.0, savefig=False):
    """Plot pitch for all points where alpha_err > angle_err_lim.
    Cyan points are with no sun presence, red are with sun presence.
    Unlike plot_pitches() below there is no distinction made based
    on the kalman state.
    """
    times = out['times']
    pitch = out['pitch']
    alpha_err = out['alpha'] - out['roll']
    sun = out['alpha_sun'] & out['beta_sun']
    bad = abs(alpha_err) > angle_err_lim

    zipvals = zip((~sun, sun),
                  ('c.', 'r.'),
                  ('c', 'r'),
                  ('No Sun Presence', 'Sun Presence'))
    plt.figure()
    for filt, mark, mec, label in zipvals:
        if sum(bad & filt) > 0:
            plot_cxctime(times[bad & filt], pitch[bad & filt], mark,
                         mec=mec, label=label)
    plt.legend(loc='lower left')
    plt.grid('on')
    plt.title("Pitch for alpha error > {} deg".format(angle_err_lim))
    plt.ylabel('Pitch (deg)')

    x0, x1 = plt.xlim()
    dx = (x1 - x0) / 20
    plt.xlim(x0 - dx, x1 + dx)
    y0, y1 = plt.ylim()
    y0 = min(y0, 133.5)
    dy = (y1 - y0) / 20
    plt.ylim(y0 - dy, y1 + dy)

    if savefig:
        plt.savefig('pitch_bad_alpha.png')


def plot_pitches(out, angle_err_lim=8.0, savefig=False):
    times = out['times']
    pitch = out['pitch']
    alpha_err = out['alpha'] - out['roll']
    alpha_sun = out['alpha_sun']
    beta_sun = out['beta_sun']

    for i, title, xlabel, ylabel in (
        (1, "Pitch for alpha error > {} deg".format(angle_err_lim), None, 'Pitch (deg)'),
        (2, 'Pitch when alpha sun presence is False', None, 'Pitch (deg)'),
        (3, 'Pitch when beta sun presence is False', None, 'Pitch (deg)')):
        plt.figure(i)
        plt.clf()
        plt.grid()
        plt.title(title)
        plt.ylabel(ylabel)
        if xlabel:
            plt.xlabel(xlabel)

    zipvals = zip((~out['kalman'],
                    out['kalman']),
                  (dict(color='c', mec='c'),  # Not Kalman, No sun presence
                   dict(color='r', mec='r')),  # Kalman, No sun presence
                  (dict(color='b', mec='b', fmt='o'), # Not Kalman, Sun presence
                   dict(color='r', mec='r', fmt='x', mew=2)), # Kalman, Sun presence
                  ('Not Kalman (cyan)',
                   'Kalman (red)'))
    sun_presence = alpha_sun & beta_sun
    bad_value = abs(alpha_err) > angle_err_lim
    for filt, opt1, opt2, label in zipvals:
        plt.figure(1)
        ok = filt & bad_value
        plot_cxctime(times[ok], pitch[ok], ',',
                     label=label, **opt1)

        ok = filt & sun_presence & bad_value
        if sum(ok) > 0:
            plot_cxctime(times[ok], pitch[ok],
                         label=label + ' & Sun Presence True',
                         **opt2)

        plt.figure(2)
        ok = filt & ~alpha_sun
        plot_cxctime(times[ok], pitch[ok], ',',
                     label=label, **opt1)

        plt.figure(3)
        ok = filt & ~beta_sun
        plot_cxctime(times[ok], pitch[ok], ',',
                     label=label, **opt1)

    suffs = ('bad_alpha_sun', 'alpha_no_sun', 'beta_no_sun')
    for i, suff in enumerate(suffs):
        plt.figure(i + 1)
        x0, x1 = plt.xlim()
        dx = (x1 - x0) / 20
        plt.xlim(x0 - dx, x1 + dx)
        y0, y1 = plt.ylim()
        y0 = min(y0, 133.5)
        dy = (y1 - y0) / 20
        plt.ylim(y0 - dy, y1 + dy)

        plt.legend(loc='best')
        if savefig:
            ident = savefig if isinstance(savefig, basestring) else ''
            plt.savefig('pitch_' + ident + suff + '.png')

def get_fssa_data(start='2011:001', stop=DateTime().date, interp=4.1,
             pitch0=100, pitch1=144):
    msids = ('aopssupm', 'aopcadmd', 'aoacaseq', 'pitch', 'roll',
             'aoalpang', 'aobetang', 'aoalpsun', 'aobetsun')
    print 'fetching data'
    x = fetch.MSIDset(msids, start, stop)

    # Resample MSIDset (values and bad flags) onto a common time sampling
    print 'starting interpolate'
    x.interpolate(interp, filter_bad=False)

    # Remove data during times of known bad or anomalous data (works as of
    # Ska.engarchive 0.19.1)
    x.filter_bad_times(table=bad_times)
    # x.filter_bad_times(table=bad_times)
    
    # Select data only in a limited pitch range
    ok = ((x['pitch'].vals > pitch0) &
          (x['pitch'].vals < pitch1))

    # Determine the logical-or of bad values for all MSIDs and use this
    # to further filter the data sample
    nvals = np.sum(ok)
    bads = np.zeros(nvals, dtype=bool)
    for msid in x.values():
        # Ignore sun position monitor for bad data because it is frequently
        # bad (not available in certain subformats including SSR)
        if msid.MSID == 'AOPSSUPM':
            continue
        print msid.msid, sum(msid.bads[ok])
        bads = bads | msid.bads[ok]
    ok[ok] = ok[ok] & ~bads

    nvals = np.sum(ok)
    colnames = ('times',
                'pitch', 'roll', 'alpha', 'beta',
                'alpha_sun', 'beta_sun', 'spm_act', 'spm_act_bad', 'kalman')
    dtypes = ('f8',
              'f4', 'f4', 'f4', 'f4',
              'bool', 'bool', 'bool', 'bool', 'bool', 'bool')
    out = np.empty(nvals, dtype=zip(colnames, dtypes))

    out['times'][:] = x['pitch'].times[ok]
    out['pitch'][:] = x['pitch'].vals[ok]
    out['roll'][:] = x['roll'].vals[ok]
    out['alpha'][:] = -x['aoalpang'].vals[ok]
    out['beta'][:] = 90 - x['aobetang'].vals[ok]
    out['alpha_sun'][:] = x['aoalpsun'].vals[ok] == 'SUN '
    out['beta_sun'][:] = x['aobetsun'].vals[ok] == 'SUN '
    out['spm_act'][:] = x['aopssupm'].vals[ok] == 'ACT '
    out['spm_act_bad'][:] = x['aopssupm'].bads[ok]
    out['kalman'][:] = ((x['aoacaseq'].vals[ok] == 'KALM') &
                        (x['aopcadmd'].vals[ok] == 'NPNT'))
    return out

def get_fssb_data(start='2012:230', stop=DateTime().date, interp=4.1,
             pitch0=100, pitch1=144):
    msids = ('aopcadmd', 'aoacaseq', 'pitch', 'roll',
             'aspefsw2a', 'aspefsw4a', 'aspefsw2b', 'aspefsw4b', 
             'ccsdsvcd', 'cotlrdsf')
    print 'fetching data'
    x = fetch.MSIDset(msids, start, stop)

    # Resample MSIDset (values and bad flags) onto a common time sampling
    print 'starting interpolate'
    x.interpolate(interp, filter_bad=False)

    # Remove data during times of known bad or anomalous data (works as of
    # Ska.engarchive 0.19.1)
    x.filter_bad_times(table=bad_times)

    # Select data only in a limited pitch range
    pitch_range = ((x['pitch'].vals > pitch0) &
                   (x['pitch'].vals < pitch1))
    
    # Compute minor frame count
    mf = mod(x['ccsdsvcd'].vals, 128)
    # Account for the fact that data interpolation is not exact and minor frame
    # count slowly slides
    actual_mf = [4, 20, 36, 52, 68, 84, 100, 116]
    for i in actual_mf:
        mf[abs(mf - i) < 4] = i
    # Select data in "good" minor frames (every other minor frame has bogus data)   
    # "good" minor frames (4, 36, 68, 100) have mod(mf, 32) = 4
    good_mf = (mod(mf, 32) == 4)
    
    # Select data in PCAD diagnostic subformat (otherwise no FSS-B telemetry)
    pcad_sfmt = x['cotlrdsf'].vals == 'PCAD'
    
    ok = pitch_range & good_mf & pcad_sfmt
    
    # Determine the logical-or of bad values for all MSIDs and use this
    # to further filter the data sample
    nvals = np.sum(ok)
    bads = np.zeros(nvals, dtype=bool)
    for msid in x.values():
        # Ignore sun position monitor for bad data because it is frequently
        # bad (not available in certain subformats including SSR)
        if msid.MSID == 'AOPSSUPM':
            continue
        print msid.msid, sum(msid.bads[ok])
        bads = bads | msid.bads[ok]
    ok[ok] = ok[ok] & ~bads

    nvals = np.sum(ok)
    colnames = ('times',
                'pitch', 'roll', 'alpha', 'beta',
                'alpha_sun', 'beta_sun', 'kalman')
    dtypes = ('f8',
              'f4', 'f4', 'f4', 'f4',
              'bool', 'bool', 'bool', 'bool', 'bool', 'bool')
    out = np.empty(nvals, dtype=zip(colnames, dtypes))

    out['times'][:] = x['pitch'].times[ok]
    out['pitch'][:] = x['pitch'].vals[ok]
    out['roll'][:] = x['roll'].vals[ok]
    out['alpha'][:] = -x['aspefsw2b'].vals[ok]
    out['beta'][:] = 90 - x['aspefsw4b'].vals[ok]
    out['alpha_sun'][:] = x['aspefsw2a'].vals[ok] == 'SUN '
    out['beta_sun'][:] = x['aspefsw4a'].vals[ok] == 'SUN '
    out['kalman'][:] = ((x['aoacaseq'].vals[ok] == 'KALM') &
                        (x['aopcadmd'].vals[ok] == 'NPNT'))
    return out