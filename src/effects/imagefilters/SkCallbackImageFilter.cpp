/*
 * Copyright 2026 Tella
 *
 * Use of this source code is governed by a BSD-style license that can be
 * found in the LICENSE file.
 */

#include "include/effects/SkImageFilters.h"

#include "include/core/SkCanvas.h"
#include "include/core/SkFlattenable.h"
#include "include/core/SkImageFilter.h"
#include "include/core/SkRect.h"
#include "include/core/SkRefCnt.h"
#include "include/core/SkScalar.h"
#include "include/core/SkShader.h"
#include "include/core/SkSize.h"
#include "include/core/SkSpan.h"
#include "src/core/SkImageFilterTypes.h"
#include "src/core/SkImageFilter_Base.h"
#include "src/core/SkReadBuffer.h"
#include "src/core/SkRectPriv.h"
#include "src/core/SkWriteBuffer.h"

#include <optional>
#include <utility>

namespace {

// A filter whose output a client draws through a callback, given its input as a shader in the
// filter's local coordinates: it can run passes of its own (reductions of the input, effects that
// keep state between frames) inside a filter graph.
class SkCallbackImageFilter final : public SkImageFilter_Base {
public:
    SkCallbackImageFilter(SkImageFilters::CallbackDrawProc proc,
                          void* context,
                          void (*releaseProc)(void*),
                          sk_sp<SkImageFilter> input,
                          SkScalar sampleRadius,
                          bool restrictOutputToInputBounds)
            : SkImageFilter_Base(&input, 1)
            , fProc(proc)
            , fContext(context)
            , fReleaseProc(releaseProc)
            , fSampleRadius(sampleRadius)
            , fRestrictOutputToInputBounds(restrictOutputToInputBounds) {}

    ~SkCallbackImageFilter() override {
        if (fReleaseProc) {
            fReleaseProc(fContext);
        }
    }

    SkRect computeFastBounds(const SkRect& src) const override {
        if (fRestrictOutputToInputBounds) {
            SkRect bounds = this->SkImageFilter::computeFastBounds(src);
            bounds.outset(fSampleRadius, fSampleRadius);
            return bounds;
        }
        return SkRectPriv::MakeLargeS32();
    }

protected:
    void flatten(SkWriteBuffer& buffer) const override {
        this->SkImageFilter_Base::flatten(buffer);
    }

private:
    SK_FLATTENABLE_HOOKS(SkCallbackImageFilter)

    bool onAffectsTransparentBlack() const override { return !fRestrictOutputToInputBounds; }

    // The client draws in local coordinates through the canvas's matrix, whatever it is.
    MatrixCapability onGetCTMCapability() const override { return MatrixCapability::kComplex; }

    skif::LayerSpace<SkIRect> withSampleRadius(const skif::Mapping& mapping,
                                               skif::LayerSpace<SkIRect> bounds) const {
        skif::LayerSpace<SkISize> radius = mapping.paramToLayer(
                skif::ParameterSpace<SkSize>({fSampleRadius, fSampleRadius})).ceil();
        bounds.outset(radius);
        return bounds;
    }

    skif::FilterResult onFilterImage(const skif::Context& ctx) const override {
        using ShaderFlags = skif::FilterResult::ShaderFlags;

        skif::Context inputCtx = ctx.withNewDesiredOutput(
                this->withSampleRadius(ctx.mapping(), ctx.desiredOutput()));
        skif::FilterResult input = this->getChildOutput(0, inputCtx);
        std::optional<skif::LayerSpace<SkIRect>> explicitOutput;
        if (fRestrictOutputToInputBounds) {
            explicitOutput = this->withSampleRadius(ctx.mapping(), input.layerBounds());
        }
        bool hasInput = SkToBool(input);

        skif::FilterResult::Builder builder{ctx};
        builder.add(std::move(input), inputCtx.desiredOutput(), ShaderFlags::kNonTrivialSampling);
        return builder.evalDrawing(
                [&](SkCanvas* canvas, SkSpan<sk_sp<SkShader>> inputs) {
                    SkShader* shader = hasInput && !inputs.empty() ? inputs[0].get() : nullptr;
                    fProc(fContext, canvas, shader);
                },
                explicitOutput);
    }

    skif::LayerSpace<SkIRect> onGetInputLayerBounds(
            const skif::Mapping& mapping,
            const skif::LayerSpace<SkIRect>& desiredOutput,
            std::optional<skif::LayerSpace<SkIRect>> contentBounds) const override {
        return this->getChildInputLayerBounds(
                0, mapping, this->withSampleRadius(mapping, desiredOutput), contentBounds);
    }

    std::optional<skif::LayerSpace<SkIRect>> onGetOutputLayerBounds(
            const skif::Mapping& mapping,
            std::optional<skif::LayerSpace<SkIRect>> contentBounds) const override {
        if (fRestrictOutputToInputBounds) {
            auto childOutput = this->getChildOutputLayerBounds(0, mapping, contentBounds);
            if (childOutput) {
                return this->withSampleRadius(mapping, *childOutput);
            }
        }
        return skif::LayerSpace<SkIRect>::Unbounded();
    }

    SkImageFilters::CallbackDrawProc fProc;
    void* fContext;
    void (*fReleaseProc)(void*);
    SkScalar fSampleRadius;
    bool fRestrictOutputToInputBounds;
};

} // end namespace

sk_sp<SkImageFilter> SkImageFilters::Callback(CallbackDrawProc proc,
                                              void* context,
                                              void (*releaseProc)(void* context),
                                              sk_sp<SkImageFilter> input,
                                              SkScalar sampleRadius,
                                              bool restrictOutputToInputBounds) {
    if (!proc || !(sampleRadius >= 0.f)) {
        if (releaseProc) {
            releaseProc(context);
        }
        return nullptr;
    }
    return sk_sp<SkImageFilter>(new SkCallbackImageFilter(proc, context, releaseProc,
                                                          std::move(input), sampleRadius,
                                                          restrictOutputToInputBounds));
}

// A callback cannot be serialized: a picture that holds one reads back without it.
sk_sp<SkFlattenable> SkCallbackImageFilter::CreateProc(SkReadBuffer& buffer) {
    buffer.validate(false);
    return nullptr;
}
